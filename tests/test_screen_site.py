from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from renewable_planner.application.spatial import (
    ScreeningExecutionError,
    ScreenSite,
    ScreenSiteCommand,
)
from renewable_planner.domain import (
    AnalysisRun,
    AnalysisRunStatus,
    ConstraintCategory,
    ConstraintLevel,
    Project,
    ScreenSiteResult,
    Site,
    SpatialConstraint,
    SpatialDataLayer,
    SpatialGeometry,
    SpatialRuleEngineResult,
)

ANALYSIS_DATE = date(2026, 8, 6)
BOUNDARY = SpatialGeometry(
    "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
    "EPSG:2180",
)


class MemoryProjectRepository:
    def __init__(self, project: Project) -> None:
        self.project = project

    def get(self, project_id: UUID) -> Project | None:
        return self.project if self.project.id == project_id else None


class MemorySiteRepository:
    def __init__(self, site: Site) -> None:
        self.site = site

    def get(self, site_id: UUID) -> Site | None:
        return self.site if self.site.id == site_id else None


class MemoryRuleProvider:
    def __init__(self, rule: SpatialConstraint) -> None:
        self.rule = rule
        self.request: tuple[str, str, date] | None = None

    def get_active(
        self, country: str, technology: str, as_of: date
    ) -> tuple[SpatialConstraint, ...]:
        self.request = (country, technology, as_of)
        return (self.rule,)


class MemoryLayerProvider:
    def __init__(self, layer: SpatialDataLayer) -> None:
        self.layer = layer
        self.requested_names: tuple[str, ...] = ()

    def get_layers(
        self,
        names: Sequence[str],
        boundary: SpatialGeometry,
        as_of: date,
    ) -> tuple[SpatialDataLayer, ...]:
        assert boundary == BOUNDARY
        assert as_of == ANALYSIS_DATE
        self.requested_names = tuple(names)
        return (self.layer,) if self.layer.name in names else ()


class MemoryAnalysisRunRepository:
    def __init__(self) -> None:
        self.history: list[AnalysisRun] = []

    def save(self, analysis_run: AnalysisRun) -> None:
        self.history.append(analysis_run)


class MemoryResultRepository:
    def __init__(self) -> None:
        self.saved: list[ScreenSiteResult] = []

    def save(self, result: ScreenSiteResult) -> None:
        self.saved.append(result)


class MemoryRuleEvaluator:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.analysis_run_id: UUID | None = None

    def evaluate(
        self,
        site: SpatialGeometry,
        rules: Sequence[SpatialConstraint],
        layers: Mapping[str, SpatialDataLayer],
        technology: str,
        analysis_date: date,
        analysis_run_id: UUID | None = None,
    ) -> SpatialRuleEngineResult:
        assert site == BOUNDARY
        assert len(rules) == 1
        assert set(layers) == {"fictional-restrictions"}
        assert technology == "wind"
        assert analysis_date == ANALYSIS_DATE
        self.analysis_run_id = analysis_run_id
        if self.failure is not None:
            raise self.failure
        return SpatialRuleEngineResult(
            findings=(),
            excluded_geometry=None,
            remaining_geometry=site,
            initial_area_square_meters=100.0,
            excluded_area_square_meters=0.0,
            available_area_square_meters=100.0,
        )


def _dependencies(
    evaluator: MemoryRuleEvaluator,
) -> tuple[ScreenSite, ScreenSiteCommand, MemoryAnalysisRunRepository, MemoryResultRepository]:
    site = Site(name="Fictional site", boundary=BOUNDARY)
    project = Project(name="Fictional project", site_ids=(site.id,))
    rule = SpatialConstraint(
        name="Fictional warning",
        category=ConstraintCategory.ENVIRONMENTAL,
        geometry=None,
        rule_version="rule-2026-01",
        source="fictional rule set",
        valid_from=date(2026, 1, 1),
        level=ConstraintLevel.WARNING,
        technologies=frozenset({"wind"}),
        required_layer="fictional-restrictions",
    )
    layer = SpatialDataLayer(
        name="fictional-restrictions",
        geometry=SpatialGeometry("POINT (50 50)", "EPSG:2180"),
        source="synthetic memory layer",
        version="layer-7",
    )
    runs = MemoryAnalysisRunRepository()
    results = MemoryResultRepository()
    first_instant = datetime(2026, 8, 6, 10, tzinfo=UTC)
    instants = iter(first_instant + timedelta(seconds=index) for index in range(10))
    use_case = ScreenSite(
        project_repository=MemoryProjectRepository(project),
        site_repository=MemorySiteRepository(site),
        rule_provider=MemoryRuleProvider(rule),
        layer_provider=MemoryLayerProvider(layer),
        rule_evaluator=evaluator,
        analysis_run_repository=runs,
        result_repository=results,
        clock=lambda: next(instants),
    )
    command = ScreenSiteCommand(
        project_id=project.id,
        site_id=site.id,
        country="pl",
        technology="Wind",
        analysis_date=ANALYSIS_DATE,
        parameters=(("requested_by", "test-suite"),),
    )
    return use_case, command, runs, results


def test_screen_site_orchestrates_and_persists_traceable_result() -> None:
    evaluator = MemoryRuleEvaluator()
    use_case, command, runs, results = _dependencies(evaluator)

    result = use_case.execute(command)

    assert [run.status for run in runs.history] == [
        AnalysisRunStatus.PENDING,
        AnalysisRunStatus.RUNNING,
        AnalysisRunStatus.RUNNING,
        AnalysisRunStatus.COMPLETED,
    ]
    assert result.analysis_run.status is AnalysisRunStatus.COMPLETED
    assert result.analysis_run.id == evaluator.analysis_run_id
    assert result.analysis_run.project_id == command.project_id
    assert result.analysis_run.site_id == command.site_id
    assert dict(result.analysis_run.parameters) == {
        "analysis_date": "2026-08-06",
        "country": "PL",
        "requested_by": "test-suite",
        "technology": "wind",
    }
    versions = dict(result.analysis_run.data_versions)
    assert versions["layer:fictional-restrictions"] == "layer-7"
    assert "rule-2026-01" in versions.values()
    assert results.saved == [result]
    assert result.spatial_result.available_area_square_meters == 100.0


def test_screen_site_records_failed_status_when_analysis_raises() -> None:
    evaluator = MemoryRuleEvaluator(failure=ValueError("fictional geometry failure"))
    use_case, command, runs, results = _dependencies(evaluator)

    with pytest.raises(ScreeningExecutionError, match="fictional geometry failure") as raised:
        use_case.execute(command)

    assert raised.value.analysis_run_id == evaluator.analysis_run_id
    assert runs.history[-1].status is AnalysisRunStatus.FAILED
    assert runs.history[-1].error_message == "fictional geometry failure"
    assert dict(runs.history[-1].data_versions)["layer:fictional-restrictions"] == "layer-7"
    assert results.saved == []
