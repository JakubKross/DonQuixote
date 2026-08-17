from datetime import date
from uuid import uuid4

import pytest

from renewable_planner.adapters.geospatial import (
    GeoPandasSpatialOperations,
    PyprojCoordinateReferenceSystemService,
)
from renewable_planner.application.spatial import SpatialDataLayer, SpatialRuleEngine
from renewable_planner.domain import (
    ConstraintCategory,
    ConstraintLevel,
    FindingStatus,
    SpatialConstraint,
    SpatialGeometry,
)

CRS = "EPSG:2180"
ANALYSIS_DATE = date(2026, 8, 6)


def _square(x_min: float, y_min: float, size: float) -> SpatialGeometry:
    x_max = x_min + size
    y_max = y_min + size
    return SpatialGeometry(
        f"POLYGON (({x_min} {y_min}, {x_max} {y_min}, {x_max} {y_max}, "
        f"{x_min} {y_max}, {x_min} {y_min}))",
        CRS,
    )


def _rule(
    level: ConstraintLevel,
    *,
    technologies: frozenset[str] = frozenset({"wind"}),
    layer_name: str = "fictional-layer",
    buffer_meters: float = 0.0,
    valid_from: date = date(2026, 1, 1),
) -> SpatialConstraint:
    return SpatialConstraint(
        name=f"Fictional {level.value} rule",
        category=ConstraintCategory.TECHNICAL,
        geometry=None,
        rule_version="rule-v1",
        source="fictional rule catalogue",
        valid_from=valid_from,
        level=level,
        technologies=technologies,
        required_layer=layer_name,
        buffer_meters=buffer_meters,
    )


def _layer(geometry: SpatialGeometry) -> SpatialDataLayer:
    return SpatialDataLayer(
        name="fictional-layer",
        geometry=geometry,
        source="synthetic test dataset",
        version="dataset-v3",
    )


def _engine() -> SpatialRuleEngine:
    operations = GeoPandasSpatialOperations(PyprojCoordinateReferenceSystemService())
    return SpatialRuleEngine(operations)


def test_exclusion_rule_removes_intersection_and_reports_areas() -> None:
    analysis_run_id = uuid4()
    rule = _rule(ConstraintLevel.EXCLUSION)

    result = _engine().evaluate(
        site=_square(0, 0, 10),
        rules=[rule],
        layers={"fictional-layer": _layer(_square(5, 0, 10))},
        technology="wind",
        analysis_date=ANALYSIS_DATE,
        analysis_run_id=analysis_run_id,
    )

    assert result.initial_area_square_meters == pytest.approx(100.0)
    assert result.excluded_area_square_meters == pytest.approx(50.0)
    assert result.available_area_square_meters == pytest.approx(50.0)
    assert result.excluded_geometry is not None
    assert result.remaining_geometry is not None
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.analysis_run_id == analysis_run_id
    assert finding.status is FindingStatus.AFFECTED
    assert finding.level is ConstraintLevel.EXCLUSION
    assert finding.data_source == "synthetic test dataset"
    assert finding.data_version == "dataset-v3"
    assert finding.analyzed_at.date() == ANALYSIS_DATE
    assert finding.constraint_id == rule.id
    assert "exclusion" in finding.message


@pytest.mark.parametrize(
    "level",
    [
        ConstraintLevel.CONDITIONAL,
        ConstraintLevel.WARNING,
        ConstraintLevel.INFORMATION,
    ],
)
def test_non_exclusion_levels_create_findings_without_removing_area(
    level: ConstraintLevel,
) -> None:
    result = _engine().evaluate(
        site=_square(0, 0, 10),
        rules=[_rule(level)],
        layers={"fictional-layer": _layer(_square(5, 0, 10))},
        technology="wind",
        analysis_date=ANALYSIS_DATE,
    )

    assert result.findings[0].status is FindingStatus.AFFECTED
    assert result.findings[0].level is level
    assert result.excluded_geometry is None
    assert result.excluded_area_square_meters == 0.0
    assert result.available_area_square_meters == pytest.approx(100.0)


def test_rule_for_another_technology_is_skipped() -> None:
    result = _engine().evaluate(
        site=_square(0, 0, 10),
        rules=[_rule(ConstraintLevel.EXCLUSION, technologies=frozenset({"solar"}))],
        layers={"fictional-layer": _layer(_square(0, 0, 10))},
        technology="wind",
        analysis_date=ANALYSIS_DATE,
    )

    assert result.findings == ()
    assert result.excluded_geometry is None
    assert result.available_area_square_meters == pytest.approx(100.0)


def test_inactive_rule_is_skipped() -> None:
    result = _engine().evaluate(
        site=_square(0, 0, 10),
        rules=[_rule(ConstraintLevel.EXCLUSION, valid_from=date(2027, 1, 1))],
        layers={},
        technology="wind",
        analysis_date=ANALYSIS_DATE,
    )

    assert result.findings == ()


def test_buffer_distance_comes_from_rule_configuration() -> None:
    without_buffer = _engine().evaluate(
        site=_square(0, 0, 10),
        rules=[_rule(ConstraintLevel.EXCLUSION)],
        layers={"fictional-layer": _layer(SpatialGeometry("POINT (15 5)", CRS))},
        technology="wind",
        analysis_date=ANALYSIS_DATE,
    )
    with_buffer = _engine().evaluate(
        site=_square(0, 0, 10),
        rules=[_rule(ConstraintLevel.EXCLUSION, buffer_meters=6.0)],
        layers={"fictional-layer": _layer(SpatialGeometry("POINT (15 5)", CRS))},
        technology="wind",
        analysis_date=ANALYSIS_DATE,
    )

    assert without_buffer.excluded_geometry is None
    assert with_buffer.excluded_geometry is not None
    assert with_buffer.excluded_area_square_meters > 0


def test_missing_required_layer_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing required spatial layer"):
        _engine().evaluate(
            site=_square(0, 0, 10),
            rules=[_rule(ConstraintLevel.WARNING)],
            layers={},
            technology="wind",
            analysis_date=ANALYSIS_DATE,
        )
