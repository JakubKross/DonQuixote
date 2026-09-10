"""Shapely adapter converting screened-site geometry into wind-layout areas."""

from collections.abc import Iterable
from typing import Any

from shapely import wkt
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from renewable_planner.domain.common import SpatialGeometry
from renewable_planner.domain.crs import NonMetricCoordinateReferenceSystemError
from renewable_planner.domain.wind_layout import AvailableArea, WindLayoutValidationError
from renewable_planner.ports.spatial import CoordinateReferenceSystemService


class AvailableAreaExtractionError(ValueError):
    """Raised when screened-site geometry cannot become a wind-layout area."""


class ShapelyAvailableAreaExtractor:
    """Convert a single metric polygon into a wind-layout ``AvailableArea``.

    The screening result may be a ``MultiPolygon`` (for example when
    exclusions split the site into disjoint parts), empty, or a non-polygon
    geometry; all of these are rejected with a clear error instead of
    silently picking one part.
    """

    def __init__(self, crs_service: CoordinateReferenceSystemService) -> None:
        self._crs_service = crs_service

    def extract(self, geometry: SpatialGeometry) -> AvailableArea:
        """Return a metric ``AvailableArea`` built from the given geometry."""
        self._require_metric(geometry)
        polygon = self._single_polygon(geometry)
        try:
            return AvailableArea(
                exterior=_ring_without_closing_point(polygon.exterior.coords),
                holes=tuple(_ring_without_closing_point(ring.coords) for ring in polygon.interiors),
            )
        except WindLayoutValidationError as error:
            raise AvailableAreaExtractionError(str(error)) from error

    def _require_metric(self, geometry: SpatialGeometry) -> None:
        definition = self._crs_service.inspect(geometry.crs)
        if not definition.is_metric:
            kind = "geographic" if definition.is_geographic else "non-metric"
            raise NonMetricCoordinateReferenceSystemError(
                f"CRS {definition.identifier} is {kind}; turbine layout requires metric units"
            )

    @staticmethod
    def _single_polygon(geometry: SpatialGeometry) -> Polygon:
        try:
            shape: BaseGeometry = wkt.loads(geometry.wkt)
        except GEOSException as error:
            raise AvailableAreaExtractionError("geometry WKT cannot be read") from error
        if shape.is_empty:
            raise AvailableAreaExtractionError("available area must not be empty")
        if isinstance(shape, MultiPolygon):
            parts = [part for part in shape.geoms if not part.is_empty]
            if len(parts) != 1:
                raise AvailableAreaExtractionError(
                    f"available area must be a single polygon; got {len(parts)} disjoint parts"
                )
            shape = parts[0]
        if not isinstance(shape, Polygon):
            raise AvailableAreaExtractionError(
                f"available area must be a polygon, got {shape.geom_type}"
            )
        return shape


def _ring_without_closing_point(coords: Iterable[Any]) -> tuple[tuple[float, float], ...]:
    points = tuple((float(point[0]), float(point[1])) for point in coords)
    if len(points) >= 2 and points[0] == points[-1]:
        points = points[:-1]
    return points
