"""Thin FastAPI web interface for the spatial screening use case (Step 1 of
the Etap 8 plan in docs/WEB_ARCHITECTURE.md).

Like the CLI and the Streamlit prototype, this interface calls only existing
use cases through :mod:`renewable_planner.composition` — no GIS logic lives
here; uploads are written to a temporary directory and handed to the same
file-based adapters (`load_site`, `write_screening_outputs`) the other two
interfaces already use.

Unlike CLI/Streamlit (one screening per process, never looked up again),
results here are kept in process-shared repositories so a screening created
by one request can be read back by a later one. By default that is the
in-memory adapters (:mod:`renewable_planner.adapters.memory_repositories`)
— an explicit, documented Step 1 limitation: state is lost on restart and
not shared across worker processes. Setting the ``DATABASE_URL`` environment
variable switches to persistent PostGIS-backed adapters instead (Step 2,
:mod:`renewable_planner.adapters.postgres`) implementing the very same
ports, with no change to the routes below beyond composition wiring — and
additionally turns ``POST /v1/screenings`` into a ``202`` + polling flow
backed by a job queue (Step 3, :mod:`renewable_planner.worker`) instead of
running the screening synchronously in the request. Without ``DATABASE_URL``
there is no second process that could read a shared queue, so that mode
stays fully synchronous (``201`` with the completed result), exactly as in
Step 1.

Run with:

    uvicorn renewable_planner.api.app:app --reload

Against Postgres instead of in-memory state (and with async job processing
— also start the worker, see renewable_planner.worker):

    DATABASE_URL=postgresql://user:pass@host/db uvicorn renewable_planner.api.app:app
    DATABASE_URL=postgresql://user:pass@host/db python -m renewable_planner.worker
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from renewable_planner.adapters.geospatial.file_screening import (
    load_site,
    write_screening_outputs,
)
from renewable_planner.adapters.geospatial.pyproj_crs_service import (
    PyprojCoordinateReferenceSystemService,
)
from renewable_planner.adapters.memory_repositories import (
    InMemoryAnalysisRunRepository,
    InMemoryProjectRepository,
    InMemoryScreeningResultRepository,
)
from renewable_planner.api.schemas import FindingSummary, ScreeningSummary
from renewable_planner.application.spatial import (
    ScreeningExecutionError,
    ScreenSiteCommand,
    ScreenSiteError,
)
from renewable_planner.composition import (
    build_file_screen_site,
    build_postgres_job_repository,
    build_postgres_repositories,
    build_text_report_generator,
)
from renewable_planner.domain import AnalysisRun, AnalysisRunStatus, ScreenSiteResult
from renewable_planner.domain.common import SpatialGeometry

if TYPE_CHECKING:
    from renewable_planner.adapters.postgres import (
        Job,
        PostgresAnalysisRunRepository,
        PostgresJobRepository,
        PostgresProjectRepository,
        PostgresScreeningResultRepository,
    )

DEFAULT_COUNTRY = "PL"
# The CRS web maps (MapLibre, Leaflet, ...) expect GeoJSON coordinates in —
# see `_for_map` below, which reprojects the layer endpoints into it.
WEB_MAP_CRS = "EPSG:4326"

app = FastAPI(
    title="DonQuixote API",
    version="0.1.0",
    description="Wstępny screening OZE — wynik pomocniczy, nie opinia prawna.",
)

# No authentication in this first version (see WEB_ARCHITECTURE.md section
# 6) — CORS is restricted to known frontend origins instead of left open, so
# only the configured frontend(s) can call this API from a browser. Default
# covers Vite's default dev server port; override for other setups.
_frontend_origins = [
    origin.strip()
    for origin in os.environ.get(
        "DONQUIXOTE_FRONTEND_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Process-shared state — see the module docstring and docs/WEB_ARCHITECTURE.md.
# ``DATABASE_URL`` set → persistent PostGIS-backed repositories (Step 2) and
# the async job queue (Step 3, ``_jobs`` not None); unset (the default) →
# in-memory ones and fully synchronous ``POST`` (Step 1), same as before
# these switches were added, so existing deployments and tests are
# unaffected.
_projects: InMemoryProjectRepository | PostgresProjectRepository
_runs: InMemoryAnalysisRunRepository | PostgresAnalysisRunRepository
_results: InMemoryScreeningResultRepository | PostgresScreeningResultRepository
_jobs: PostgresJobRepository | None
_uploads_dir: Path | None

_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    _projects, _runs, _results = build_postgres_repositories(_database_url)
    _jobs = build_postgres_job_repository(_database_url)
    # Durable — unlike the per-request tempdir used below for sync mode,
    # these files must survive until a worker process (possibly started
    # later, possibly on a retry) reads them.
    _uploads_dir = Path(os.environ.get("DONQUIXOTE_JOB_STORAGE", tempfile.gettempdir()))
    _uploads_dir = _uploads_dir / "donquixote-jobs"
    _uploads_dir.mkdir(parents=True, exist_ok=True)
else:
    _projects = InMemoryProjectRepository()
    _runs = InMemoryAnalysisRunRepository()
    _results = InMemoryScreeningResultRepository()
    _jobs = None
    _uploads_dir = None


@app.get("/")
def health() -> dict[str, str]:
    """Trivial liveness check."""
    return {"status": "ok"}


@app.post("/v1/screenings", response_model=ScreeningSummary)
async def create_screening(
    response: Response,
    site: Annotated[UploadFile, File(description="Granica terenu (GeoJSON)")],
    constraints: Annotated[UploadFile, File(description="Warstwy ograniczeń (GeoJSON)")],
    rules: Annotated[UploadFile, File(description="Konfiguracja reguł (YAML)")],
    technology: Annotated[str, Form()],
    country: Annotated[str, Form()] = DEFAULT_COUNTRY,
    analysis_date: Annotated[date | None, Form()] = None,
) -> ScreeningSummary:
    """Create a screening.

    Without ``DATABASE_URL`` (Step 1): runs synchronously, like the CLI, and
    returns ``201`` with the completed result. With ``DATABASE_URL`` (Step
    3): only validates the input, enqueues a job and returns ``202`` with a
    ``pending`` summary — a worker process picks it up and ``GET`` polls for
    the outcome.
    """
    if not technology.strip():
        raise HTTPException(422, "technology must not be empty")

    if _jobs is None:
        return await _create_screening_synchronously(
            response, site, constraints, rules, technology, country, analysis_date
        )
    return await _create_screening_job(
        response, site, constraints, rules, technology, country, analysis_date
    )


async def _create_screening_synchronously(
    response: Response,
    site: UploadFile,
    constraints: UploadFile,
    rules: UploadFile,
    technology: str,
    country: str,
    analysis_date: date | None,
) -> ScreeningSummary:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        site_path = tmp_dir / "site.geojson"
        constraints_path = tmp_dir / "constraints.geojson"
        rules_path = tmp_dir / "rules.yaml"
        site_path.write_bytes(await site.read())
        constraints_path.write_bytes(await constraints.read())
        rules_path.write_bytes(await rules.read())

        try:
            site_model = load_site(site_path)
            use_case, project = build_file_screen_site(
                site_model,
                site_path,
                constraints_path,
                rules_path,
                analysis_run_repository=_runs,
                result_repository=_results,
            )
            _projects.add(project)
            result = use_case.execute(
                ScreenSiteCommand(
                    project_id=project.id,
                    site_id=site_model.id,
                    country=country,
                    technology=technology,
                    analysis_date=analysis_date or date.today(),
                )
            )
        except ScreeningExecutionError as error:
            # The run was already saved as `failed` by ScreenSite itself, so
            # the client can still GET it by id even though POST reports an
            # error for this request.
            raise HTTPException(
                422,
                detail={"message": str(error), "id": str(error.analysis_run_id)},
            ) from error
        except (ScreenSiteError, ValueError, OSError) as error:
            raise HTTPException(422, detail=str(error)) from error

    response.status_code = status.HTTP_201_CREATED
    return _summary(result.analysis_run, result)


async def _create_screening_job(
    response: Response,
    site: UploadFile,
    constraints: UploadFile,
    rules: UploadFile,
    technology: str,
    country: str,
    analysis_date: date | None,
) -> ScreeningSummary:
    assert _jobs is not None and _uploads_dir is not None  # narrowed by the caller

    job_id = uuid4()
    job_dir = _uploads_dir / str(job_id)
    job_dir.mkdir(parents=True)
    site_path = job_dir / "site.geojson"
    constraints_path = job_dir / "constraints.geojson"
    rules_path = job_dir / "rules.yaml"
    site_path.write_bytes(await site.read())
    constraints_path.write_bytes(await constraints.read())
    rules_path.write_bytes(await rules.read())

    try:
        # Validated eagerly, same as the synchronous path, so a malformed
        # upload is rejected with a `422` on `POST` rather than failing
        # silently later inside the worker.
        site_model = load_site(site_path)
        _, project = build_file_screen_site(site_model, site_path, constraints_path, rules_path)
    except (ScreenSiteError, ValueError, OSError) as error:
        raise HTTPException(422, detail=str(error)) from error
    _projects.add(project)

    effective_date = analysis_date or date.today()
    _jobs.enqueue(
        job_id,
        "screening",
        {
            "site_path": str(site_path),
            "constraints_path": str(constraints_path),
            "rules_path": str(rules_path),
            "project_id": str(project.id),
            "site_id": str(site_model.id),
            "technology": technology,
            "country": country,
            "analysis_date": effective_date.isoformat(),
        },
    )

    response.status_code = status.HTTP_202_ACCEPTED
    response.headers["Location"] = f"/v1/screenings/{job_id}"
    pending_run = AnalysisRun(
        id=job_id,
        project_id=project.id,
        site_id=site_model.id,
        technology=technology.strip().lower(),
        country=country.strip().upper(),
        status=AnalysisRunStatus.PENDING,
        started_at=None,
    )
    return _summary(pending_run, None)


@app.get("/v1/screenings/{screening_id}", response_model=ScreeningSummary)
def get_screening(screening_id: UUID) -> ScreeningSummary:
    """Look up a previously created screening by id.

    ``screening_id`` is either an ``AnalysisRun`` id (sync mode, or async
    mode once resolved) or — only when the job queue is enabled — a job id
    that has not resolved to a run yet (``pending``/``running``).
    """
    run = _runs.get(screening_id)
    if run is not None:
        return _summary(run, _results.get(screening_id))

    if _jobs is not None:
        job = _jobs.get(screening_id)
        if job is not None:
            return _job_summary(job)

    raise HTTPException(status.HTTP_404_NOT_FOUND, "screening not found")


@app.get("/v1/screenings/{screening_id}/report", response_class=PlainTextResponse)
def get_screening_report(screening_id: UUID) -> str:
    """Render the plain-text report for a completed screening."""
    run = _resolve_run(screening_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "screening not found")
    result = _results.get(run.id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "screening has no result yet")
    project = _projects.get(run.project_id) if run.project_id is not None else None
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found for this screening")
    return build_text_report_generator().execute(project, result)


@app.get("/v1/screenings/{screening_id}/layers/{layer}")
def get_screening_layer(screening_id: UUID, layer: str) -> dict[str, Any]:
    """Return one result layer as GeoJSON, for map display."""
    if layer not in {"available", "excluded"}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown layer")
    run = _resolve_run(screening_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "screening not found")
    result = _results.get(run.id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "screening has no result yet")

    filename = "available_area.geojson" if layer == "available" else "excluded_areas.geojson"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        write_screening_outputs(_for_map(result), tmp_dir)
        document: dict[str, Any] = json.loads((tmp_dir / filename).read_text(encoding="utf-8"))
        return document


def _for_map(result: ScreenSiteResult) -> ScreenSiteResult:
    """Reproject a result's geometries to WGS84 for GeoJSON map display.

    The analysis CRS (e.g. ``EPSG:2180`` for Poland) is metric, required for
    area/buffer math — but wrong for a web map, which expects WGS84
    lon/lat. Only this on-the-fly response is reprojected; everything else
    (the report, the area figures in ``ScreeningSummary``) keeps using the
    analysis CRS, where it belongs.
    """
    crs_service = PyprojCoordinateReferenceSystemService()

    def transform(geometry: SpatialGeometry | None) -> SpatialGeometry | None:
        return None if geometry is None else crs_service.transform(geometry, WEB_MAP_CRS)

    spatial = result.spatial_result
    reprojected = replace(
        spatial,
        excluded_geometry=transform(spatial.excluded_geometry),
        remaining_geometry=transform(spatial.remaining_geometry),
    )
    return replace(result, spatial_result=reprojected)


def _resolve_run(screening_id: UUID) -> AnalysisRun | None:
    """Resolve a client-visible screening id to its ``AnalysisRun``.

    Handles both an id that already is an ``AnalysisRun`` id, and — only
    when the job queue is enabled — a job id whose job has finished and
    points at one via ``jobs.analysis_run_id``.
    """
    run = _runs.get(screening_id)
    if run is not None:
        return run
    if _jobs is None:
        return None
    job = _jobs.get(screening_id)
    if job is None or job.analysis_run_id is None:
        return None
    return _runs.get(job.analysis_run_id)


def _job_summary(job: Job) -> ScreeningSummary:
    """Build the response for a job that has not resolved to a readable
    ``AnalysisRun`` yet (``queued``/``running``), or defensively for a
    terminal job whose run could not be found."""
    if job.analysis_run_id is not None:
        run = _runs.get(job.analysis_run_id)
        if run is not None:
            return _summary(run, _results.get(job.analysis_run_id), summary_id=job.id)

    status_label = {"queued": "pending", "running": "running"}.get(job.status, job.status)
    payload = job.payload
    return ScreeningSummary(
        id=job.id,
        project_id=UUID(payload["project_id"]),
        site_id=UUID(payload["site_id"]),
        technology=payload["technology"],
        country=payload["country"],
        status=status_label,
        error_message=job.last_error if job.status == "failed" else None,
    )


def _summary(
    run: AnalysisRun,
    result: ScreenSiteResult | None,
    *,
    summary_id: UUID | None = None,
) -> ScreeningSummary:
    spatial = result.spatial_result if result is not None else None
    warnings = None
    findings: list[FindingSummary] = []
    if spatial is not None:
        warnings = sum(
            finding.level.value == "warning" and finding.status.value == "affected"
            for finding in spatial.findings
        )
        findings = [
            FindingSummary(
                id=finding.id,
                constraint_id=finding.constraint_id,
                level=finding.level.value,
                status=finding.status.value,
                data_source=finding.data_source,
                data_version=finding.data_version,
                message=finding.message,
            )
            for finding in spatial.findings
        ]
    return ScreeningSummary(
        id=summary_id or run.id,
        project_id=run.project_id,
        site_id=run.site_id,
        technology=run.technology or "",
        country=run.country or "",
        status=run.status.value,
        error_message=run.error_message,
        initial_area_square_meters=spatial.initial_area_square_meters if spatial else None,
        excluded_area_square_meters=spatial.excluded_area_square_meters if spatial else None,
        available_area_square_meters=spatial.available_area_square_meters if spatial else None,
        warnings=warnings,
        findings=findings,
    )
