"""Metric coordinate-system guard for spatial use cases."""

from renewable_planner.domain.common import SpatialGeometry
from renewable_planner.domain.crs import (
    CrsDefinition,
    NonMetricCoordinateReferenceSystemError,
)
from renewable_planner.ports.spatial import CoordinateReferenceSystemService


class MetricSpatialContext:
    """Prepare geometries for metric area, distance and buffer operations."""

    def __init__(
        self,
        crs_service: CoordinateReferenceSystemService,
        analysis_crs: str,
    ) -> None:
        self._crs_service = crs_service
        self._analysis_crs = crs_service.inspect(analysis_crs)
        self._require_metric_definition(self._analysis_crs)

    @property
    def analysis_crs(self) -> CrsDefinition:
        """Return the explicitly configured analytical CRS."""
        return self._analysis_crs

    def require_metric(self, geometry: SpatialGeometry) -> None:
        """Ensure geometry is already expressed in metric coordinates."""
        definition = self._crs_service.inspect(geometry.crs)
        self._require_metric_definition(definition)

    def to_analysis_crs(self, geometry: SpatialGeometry) -> SpatialGeometry:
        """Transform geometry to the configured metric analytical CRS."""
        source = self._crs_service.inspect(geometry.crs)
        if source.identifier == self._analysis_crs.identifier:
            self._require_metric_definition(source)
            return geometry

        transformed = self._crs_service.transform(
            geometry,
            self._analysis_crs.identifier,
        )
        self.require_metric(transformed)
        return transformed

    @staticmethod
    def _require_metric_definition(definition: CrsDefinition) -> None:
        if not definition.is_metric:
            kind = "geographic" if definition.is_geographic else "non-metric"
            raise NonMetricCoordinateReferenceSystemError(
                f"CRS {definition.identifier} is {kind}; metric units are required"
            )
