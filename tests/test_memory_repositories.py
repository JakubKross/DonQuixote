from datetime import UTC, datetime, timedelta
from uuid import uuid4

from renewable_planner.adapters.memory_repositories import (
    InMemoryAnalysisRunRepository,
    InMemoryProjectRepository,
    InMemoryScreeningResultRepository,
)
from renewable_planner.domain import (
    AnalysisRun,
    AnalysisRunStatus,
    Project,
    ScreenSiteResult,
    SpatialRuleEngineResult,
)
from renewable_planner.ports import (
    AnalysisRunQuery,
    AnalysisRunRepository,
    ProjectRepository,
    ScreeningResultQuery,
    SiteScreeningResultRepository,
)

START = datetime(2026, 1, 1, tzinfo=UTC)


def test_project_repository_round_trips_and_implements_the_port() -> None:
    repository = InMemoryProjectRepository()
    project = Project(name="Testowy projekt")

    assert isinstance(repository, ProjectRepository)
    assert repository.get(project.id) is None

    repository.add(project)

    assert repository.get(project.id) is project


def test_analysis_run_repository_keeps_the_latest_state_per_id() -> None:
    repository = InMemoryAnalysisRunRepository()
    run = AnalysisRun(status=AnalysisRunStatus.PENDING, started_at=None)

    assert isinstance(repository, AnalysisRunRepository)
    assert isinstance(repository, AnalysisRunQuery)
    assert repository.get(run.id) is None

    repository.save(run)
    assert repository.get(run.id) is run

    started = run.start(START)
    repository.save(started)

    assert repository.get(run.id) is started
    assert repository.get(run.id).status is AnalysisRunStatus.RUNNING


def test_screening_result_repository_keyed_by_analysis_run_id() -> None:
    repository = InMemoryScreeningResultRepository()
    run = AnalysisRun(
        status=AnalysisRunStatus.COMPLETED,
        started_at=START,
        finished_at=START + timedelta(hours=1),
    )
    spatial = SpatialRuleEngineResult(
        findings=(),
        excluded_geometry=None,
        remaining_geometry=None,
        initial_area_square_meters=100.0,
        excluded_area_square_meters=0.0,
        available_area_square_meters=100.0,
    )
    result = ScreenSiteResult(analysis_run=run, spatial_result=spatial)

    assert isinstance(repository, SiteScreeningResultRepository)
    assert isinstance(repository, ScreeningResultQuery)
    assert repository.get(run.id) is None

    repository.save(result)

    assert repository.get(run.id) is result
    assert repository.get(uuid4()) is None


def test_project_repository_returns_none_for_unknown_id() -> None:
    repository = InMemoryProjectRepository()

    assert repository.get(uuid4()) is None
