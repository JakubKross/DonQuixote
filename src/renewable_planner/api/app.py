"""Thin FastAPI web interface for the spatial screening use case (Step 1 of
the Etap 8 plan in docs/WEB_ARCHITECTURE.md).

Like the CLI and the Streamlit prototype, this interface calls only existing
use cases through :mod:`renewable_planner.composition` — no GIS logic lives
here; uploads are written to a temporary directory and handed to the same
file-based adapters (`load_site`, `write_screening_outputs`) the other two
interfaces already use.

Unlike CLI/Streamlit (one screening per process, never looked up again),
results here are kept in process-shared in-memory repositories
(:mod:`renewable_planner.adapters.memory_repositories`) so a screening
created by one request can be read back by a later one — an explicit,
documented Step 1 limitation: state is lost on restart and not shared across
worker processes. Step 2 (PostGIS) replaces these with persistent adapters
implementing the very same ports, with no change to the routes below beyond
composition wiring.

Run with:

    uvicorn renewable_planner.api.app:app --reload
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse

from renewable_planner.adapters.geospatial.file_screening import (
    load_site,
    write_screening_outputs,
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
from renewable_planner.composition import build_file_screen_site, build_text_report_generator
from renewable_planner.domain import AnalysisRun, ScreenSiteResult

DEFAULT_COUNTRY = "PL"

app = FastAPI(
    title="DonQuixote API",
    version="0.1.0",
    description="Wstępny screening OZE — wynik pomocniczy, nie opinia prawna.",
)

# Process-shared state — see the module docstring and docs/WEB_ARCHITECTURE.md.
_projects = InMemoryProjectRepository()
_runs = InMemoryAnalysisRunRepository()
_results = InMemoryScreeningResultRepository()


@app.get("/")
def health() -> dict[str, str]:
    """Trivial liveness check."""
    return {"status": "ok"}


@app.post(
    "/v1/screenings",
    response_model=ScreeningSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_screening(
    site: Annotated[UploadFile, File(description="Granica terenu (GeoJSON)")],
    constraints: Annotated[UploadFile, File(description="Warstwy ograniczeń (GeoJSON)")],
    rules: Annotated[UploadFile, File(description="Konfiguracja reguł (YAML)")],
    technology: Annotated[str, Form()],
    country: Annotated[str, Form()] = DEFAULT_COUNTRY,
    analysis_date: Annotated[date | None, Form()] = None,
) -> ScreeningSummary:
    """Run a screening synchronously and return its standardized summary.

    Step 1 is deliberately synchronous (like the CLI) — Step 3 of the plan
    introduces a job queue and turns this into a ``202`` + polling flow
    without changing the request/response shapes here.
    """
    if not technology.strip():
        raise HTTPException(422, "technology must not be empty")

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

    return _summary(result.analysis_run, result)


@app.get("/v1/screenings/{screening_id}", response_model=ScreeningSummary)
def get_screening(screening_id: UUID) -> ScreeningSummary:
    """Look up a previously created screening by id."""
    run = _runs.get(screening_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "screening not found")
    return _summary(run, _results.get(screening_id))


@app.get("/v1/screenings/{screening_id}/report", response_class=PlainTextResponse)
def get_screening_report(screening_id: UUID) -> str:
    """Render the plain-text report for a completed screening."""
    run = _runs.get(screening_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "screening not found")
    result = _results.get(screening_id)
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
    result = _results.get(screening_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "screening has no result yet")

    filename = "available_area.geojson" if layer == "available" else "excluded_areas.geojson"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        write_screening_outputs(result, tmp_dir)
        document: dict[str, Any] = json.loads((tmp_dir / filename).read_text(encoding="utf-8"))
        return document


def _summary(run: AnalysisRun, result: ScreenSiteResult | None) -> ScreeningSummary:
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
        id=run.id,
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
