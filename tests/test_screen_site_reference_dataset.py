import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import geopandas
import pytest
from shapely import union_all

from renewable_planner.adapters.geospatial import (
    GeoPandasSpatialOperations,
    PyprojCoordinateReferenceSystemService,
)
from renewable_planner.application.spatial import ScreenSite, ScreenSiteCommand, SpatialRuleEngine
from renewable_planner.domain import (
    AnalysisRun,
    ConstraintCategory,
    ConstraintLevel,
    FindingStatus,
    Project,
    ScreenSiteResult,
    Site,
    SpatialConstraint,
    SpatialDataLayer,
    SpatialGeometry,
)

DATASET = Path(__file__).parent / "fixtures" / "synthetic_reference_dataset.geojson"
ANALYSIS_DATE = date(2026, 8, 17)
EXPECTED_RULE_IDS = {
    UUID("10000000-0000-0000-0000-000000000001"),
    UUID("10000000-0000-0000-0000-000000000002"),
    UUID("10000000-0000-0000-0000-000000000003"),
}


class DatasetProjectRepository:
    def __init__(self, project: Project) -> None:
        self._project = project

    def get(self, project_id: UUID) -> Project | None:
        return self._project if project_id == self._project.id else None


class DatasetSiteRepository:
    def __init__(self, site: Site) -> None:
        self._site = site

    def get(self, site_id: UUID) -> Site | None:
        return self._site if site_id == self._site.id else None


class DatasetRuleProvider:
    def __init__(self, rules: tuple[SpatialConstraint, ...]) -> None:
        self._rules = rules

    def get_active(
        self, country: str, technology: str, as_of: date
    ) -> tuple[SpatialConstraint, ...]:
        assert country == "PL"
        assert technology == "wind"
        return tuple(rule for rule in self._rules if rule.is_active_on(as_of))


class DatasetLayerProvider:
    def __init__(self, layers: Mapping[str, SpatialDataLayer]) -> None:
        self._layers = layers

    def get_layers(
        self,
        names: Sequence[str],
        boundary: SpatialGeometry,
        as_of: date,
    ) -> tuple[SpatialDataLayer, ...]:
        assert boundary.crs == "EPSG:2180"
        assert as_of == ANALYSIS_DATE
        return tuple(self._layers[name] for name in names)


class MemoryAnalysisRunRepository:
    def __init__(self) -> None:
        self.saved: list[AnalysisRun] = []

    def save(self, analysis_run: AnalysisRun) -> None:
        self.saved.append(analysis_run)


class MemoryResultRepository:
    def __init__(self) -> None:
        self.saved: list[ScreenSiteResult] = []

    def save(self, result: ScreenSiteResult) -> None:
        self.saved.append(result)


def _geometry(frame: geopandas.GeoDataFrame) -> SpatialGeometry:
    return SpatialGeometry(union_all(frame.geometry.tolist()).wkt, "EPSG:2180")


def _dataset() -> tuple[Site, Project, tuple[SpatialConstraint, ...], dict[str, SpatialDataLayer]]:
    frame = geopandas.read_file(DATASET)
    site_frame = frame[frame["entity_type"] == "site"]
    site = Site(
        id=UUID(site_frame.iloc[0]["entity_id"]),
        name=str(site_frame.iloc[0]["name"]),
        boundary=_geometry(site_frame),
    )
    project = Project(name="Fikcyjny projekt Bursztynowy", site_ids=(site.id,))

    layers: dict[str, SpatialDataLayer] = {}
    layer_specs = {
        "buildings": "building",
        "environmental-area": "environmental_area",
        "infrastructure": "infrastructure",
    }
    for layer_name, entity_type in layer_specs.items():
        layer_frame = frame[frame["entity_type"] == entity_type]
        first = layer_frame.iloc[0]
        layers[layer_name] = SpatialDataLayer(
            name=layer_name,
            geometry=_geometry(layer_frame),
            source=str(first["source"]),
            version=str(first["version"]),
        )

    document = json.loads(DATASET.read_text(encoding="utf-8"))
    rules = tuple(
        SpatialConstraint(
            id=UUID(raw["id"]),
            name=raw["name"],
            category=ConstraintCategory(raw["category"]),
            geometry=None,
            rule_version=raw["rule_version"],
            source=raw["source"],
            valid_from=date.fromisoformat(raw["valid_from"]),
            level=ConstraintLevel(raw["level"]),
            technologies=frozenset({"wind"}),
            required_layer=raw["required_layer"],
            buffer_meters=raw["buffer_meters"],
        )
        for raw in document["rules"]
    )
    return site, project, rules, layers


def test_screen_site_reference_dataset_regression(tmp_path: Path) -> None:
    site, project, rules, layers = _dataset()
    runs = MemoryAnalysisRunRepository()
    results = MemoryResultRepository()
    use_case = ScreenSite(
        project_repository=DatasetProjectRepository(project),
        site_repository=DatasetSiteRepository(site),
        rule_provider=DatasetRuleProvider(rules),
        layer_provider=DatasetLayerProvider(layers),
        rule_evaluator=SpatialRuleEngine(
            GeoPandasSpatialOperations(PyprojCoordinateReferenceSystemService())
        ),
        analysis_run_repository=runs,
        result_repository=results,
        clock=lambda: datetime(2026, 8, 17, 12, tzinfo=UTC),
    )

    result = use_case.execute(
        ScreenSiteCommand(
            project_id=project.id,
            site_id=site.id,
            country="pl",
            technology="Wind",
            analysis_date=ANALYSIS_DATE,
        )
    )

    findings = result.spatial_result.findings
    assert len([finding for finding in findings if finding.status is FindingStatus.AFFECTED]) == 3
    assert {finding.constraint_id for finding in findings} == EXPECTED_RULE_IDS
    assert result.spatial_result.available_area_square_meters == pytest.approx(6962.3614, abs=0.001)
    assert dict(result.analysis_run.data_versions) == {
        "layer:buildings": "buildings-2026.01",
        "layer:environmental-area": "environment-2026.01",
        "layer:infrastructure": "infrastructure-2026.01",
        "rule:10000000-0000-0000-0000-000000000001": "rule-buildings-2026.01",
        "rule:10000000-0000-0000-0000-000000000002": "rule-environment-2026.01",
        "rule:10000000-0000-0000-0000-000000000003": "rule-infrastructure-2026.01",
    }

    output = tmp_path / "screen-site-result.json"
    output.write_text(
        json.dumps(
            {
                "analysis_run_id": str(result.analysis_run.id),
                "available_area_square_meters": result.spatial_result.available_area_square_meters,
                "findings": [
                    {"constraint_id": str(finding.constraint_id), "status": finding.status.value}
                    for finding in findings
                ],
                "data_versions": dict(result.analysis_run.data_versions),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    saved_document = json.loads(output.read_text(encoding="utf-8"))
    assert saved_document["analysis_run_id"] == str(result.analysis_run.id)
    assert len(saved_document["findings"]) == 3
    assert results.saved == [result]
