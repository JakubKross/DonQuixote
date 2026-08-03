import pytest

from renewable_planner.application.spatial import MetricSpatialContext
from renewable_planner.domain import (
    CrsDefinition,
    NonMetricCoordinateReferenceSystemError,
    SpatialGeometry,
)


class StubCrsService:
    def inspect(self, crs: str | None) -> CrsDefinition:
        definitions = {
            "EPSG:4326": CrsDefinition("EPSG:4326", True, ("degree", "degree")),
            "EPSG:2180": CrsDefinition("EPSG:2180", False, ("metre", "metre")),
        }
        if crs is None:
            raise AssertionError("unexpected missing CRS")
        return definitions[crs]

    def transform(
        self,
        geometry: SpatialGeometry,
        target_crs: str,
    ) -> SpatialGeometry:
        return SpatialGeometry(geometry.wkt, target_crs)


def test_metric_context_rejects_geographic_analysis_crs() -> None:
    with pytest.raises(NonMetricCoordinateReferenceSystemError, match="geographic"):
        MetricSpatialContext(StubCrsService(), "EPSG:4326")


def test_metric_context_accepts_metric_analysis_crs() -> None:
    context = MetricSpatialContext(StubCrsService(), "EPSG:2180")

    assert context.analysis_crs.identifier == "EPSG:2180"
    assert context.analysis_crs.is_metric


def test_metric_context_transforms_geometry_before_metric_operations() -> None:
    context = MetricSpatialContext(StubCrsService(), "EPSG:2180")
    geographic = SpatialGeometry("POINT (19 52)", "EPSG:4326")

    transformed = context.to_analysis_crs(geographic)

    assert transformed.crs == "EPSG:2180"
    context.require_metric(transformed)


def test_metric_guard_rejects_untransformed_geographic_geometry() -> None:
    context = MetricSpatialContext(StubCrsService(), "EPSG:2180")

    with pytest.raises(NonMetricCoordinateReferenceSystemError):
        context.require_metric(SpatialGeometry("POINT (19 52)", "EPSG:4326"))
