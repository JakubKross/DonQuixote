"""Integration tests for the PostGIS-backed adapters (Step 2 of
docs/WEB_ARCHITECTURE.md).

Requires Docker (an ephemeral PostGIS container via testcontainers) — see
that document's section 3.4. Skipped, like the ``pywake``/``pvlib`` marked
tests, when the optional dependency (here: a reachable Docker daemon) is not
available, rather than failing the suite.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytestmark = pytest.mark.postgres
psycopg = pytest.importorskip("psycopg")
pytest.importorskip("testcontainers")

from renewable_planner.adapters.postgres import (  # noqa: E402
    PostgresAnalysisRunRepository,
    PostgresProjectRepository,
    PostgresScreeningResultRepository,
    PostgresTechnologyResultRepository,
)
from renewable_planner.adapters.postgres.schema import SCHEMA_SQL  # noqa: E402
from renewable_planner.domain import (  # noqa: E402
    AnalysisRun,
    AnalysisRunStatus,
    ConstraintFinding,
    ConstraintLevel,
    FindingStatus,
    Project,
    ScreenSiteResult,
    SpatialGeometry,
    SpatialRuleEngineResult,
)
from renewable_planner.ports import (  # noqa: E402
    AnalysisRunQuery,
    AnalysisRunRepository,
    ProjectRepository,
    ScreeningResultQuery,
    SiteScreeningResultRepository,
)

START = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def dsn() -> Iterator[str]:
    from testcontainers.community.postgres import PostgresContainer

    try:
        container = PostgresContainer("postgis/postgis:16-3.4")
        container.start()
    except Exception as error:  # pragma: no cover - environment-dependent
        pytest.skip(f"Docker/PostGIS container unavailable: {error}")

    try:
        url = container.get_connection_url(driver=None)
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        yield url
    finally:
        container.stop()


def test_project_repository_round_trips_and_implements_the_port(dsn: str) -> None:
    repository = PostgresProjectRepository(dsn)
    project = Project(name="Testowy projekt", description="Opis")

    assert isinstance(repository, ProjectRepository)
    assert repository.get(project.id) is None

    repository.add(project)

    assert repository.get(project.id) == project
    assert repository.get(uuid4()) is None


def test_analysis_run_repository_keeps_the_latest_state_per_id(dsn: str) -> None:
    repository = PostgresAnalysisRunRepository(dsn)
    run = AnalysisRun(
        status=AnalysisRunStatus.PENDING,
        started_at=None,
        technology="wind",
        country="PL",
        parameters=(("buffer_m", "150"), ("technology", "wind")),
    )

    assert isinstance(repository, AnalysisRunRepository)
    assert isinstance(repository, AnalysisRunQuery)
    assert repository.get(run.id) is None

    repository.save(run)
    assert repository.get(run.id) == run

    started = run.start(START)
    repository.save(started)

    fetched = repository.get(run.id)
    assert fetched == started
    assert fetched is not None
    assert fetched.status is AnalysisRunStatus.RUNNING
    assert fetched.parameters == run.parameters


def test_screening_result_repository_round_trips_geometry_and_findings(dsn: str) -> None:
    analysis_run_repository = PostgresAnalysisRunRepository(dsn)
    repository = PostgresScreeningResultRepository(dsn, analysis_run_repository)

    run = AnalysisRun(
        status=AnalysisRunStatus.COMPLETED,
        started_at=START,
        finished_at=START + timedelta(hours=1),
    )
    analysis_run_repository.save(run)

    excluded = SpatialGeometry(wkt="POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))", crs="EPSG:2180")
    remaining = SpatialGeometry(wkt="POLYGON ((2 2, 3 2, 3 3, 2 3, 2 2))", crs="EPSG:2180")
    finding = ConstraintFinding(
        analysis_run_id=run.id,
        constraint_id=uuid4(),
        status=FindingStatus.AFFECTED,
        message="Teren w buforze zabudowy",
        analyzed_at=START,
        affected_geometry=excluded,
        level=ConstraintLevel.EXCLUSION,
        data_source="test",
        data_version="v1",
        requires_expert_review=True,
    )
    spatial = SpatialRuleEngineResult(
        findings=(finding,),
        excluded_geometry=excluded,
        remaining_geometry=remaining,
        initial_area_square_meters=100.0,
        excluded_area_square_meters=40.0,
        available_area_square_meters=60.0,
    )
    result = ScreenSiteResult(analysis_run=run, spatial_result=spatial)

    assert isinstance(repository, SiteScreeningResultRepository)
    assert isinstance(repository, ScreeningResultQuery)
    assert repository.get(run.id) is None

    repository.save(result)
    fetched = repository.get(run.id)

    assert fetched is not None
    assert fetched.analysis_run == run
    assert fetched.spatial_result.initial_area_square_meters == 100.0
    assert fetched.spatial_result.excluded_area_square_meters == 40.0
    assert fetched.spatial_result.available_area_square_meters == 60.0
    assert fetched.spatial_result.excluded_geometry == excluded
    assert fetched.spatial_result.remaining_geometry == remaining
    assert len(fetched.spatial_result.findings) == 1
    assert fetched.spatial_result.findings[0] == finding

    assert repository.get(uuid4()) is None


def test_screening_result_repository_handles_no_available_area(dsn: str) -> None:
    analysis_run_repository = PostgresAnalysisRunRepository(dsn)
    repository = PostgresScreeningResultRepository(dsn, analysis_run_repository)

    run = AnalysisRun(
        status=AnalysisRunStatus.COMPLETED,
        started_at=START,
        finished_at=START + timedelta(hours=1),
    )
    analysis_run_repository.save(run)

    spatial = SpatialRuleEngineResult(
        findings=(),
        excluded_geometry=None,
        remaining_geometry=None,
        initial_area_square_meters=100.0,
        excluded_area_square_meters=100.0,
        available_area_square_meters=0.0,
    )
    repository.save(ScreenSiteResult(analysis_run=run, spatial_result=spatial))

    fetched = repository.get(run.id)
    assert fetched is not None
    assert fetched.spatial_result.excluded_geometry is None
    assert fetched.spatial_result.remaining_geometry is None
    assert fetched.spatial_result.findings == ()


def test_analysis_run_repository_lists_recent_runs_newest_first(dsn: str) -> None:
    repository = PostgresAnalysisRunRepository(dsn)
    # Far in the future so they sort ahead of runs saved by other tests.
    older = AnalysisRun(created_at=START + timedelta(days=3650))
    newer = AnalysisRun(created_at=START + timedelta(days=3651))
    repository.save(older)
    repository.save(newer)

    recent = repository.list_recent(2)

    assert [run.id for run in recent] == [newer.id, older.id]
    assert recent[0] == newer


def test_technology_result_repository_saves_replaces_and_deletes(dsn: str) -> None:
    runs = PostgresAnalysisRunRepository(dsn)
    repository = PostgresTechnologyResultRepository(dsn)
    run = AnalysisRun(
        status=AnalysisRunStatus.COMPLETED,
        started_at=START,
        finished_at=START + timedelta(hours=1),
    )
    runs.save(run)

    assert repository.get(run.id, "wind") is None
    repository.save(run.id, "wind", {"turbine_count": 3, "positions": [{"x_m": 1.0}]})
    repository.save(run.id, "wind", {"turbine_count": 4})
    repository.save(run.id, "hybrid", {"sources": ["wind"]})

    assert repository.get(run.id, "wind") == {"turbine_count": 4}
    repository.delete(run.id, ("hybrid", "battery"))
    assert repository.get(run.id, "hybrid") is None
    assert repository.get(run.id, "wind") == {"turbine_count": 4}
