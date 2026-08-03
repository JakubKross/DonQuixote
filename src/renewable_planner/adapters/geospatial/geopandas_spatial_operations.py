"""GeoPandas and Shapely implementation of spatial operations."""

import logging
from collections.abc import Sequence

import geopandas
from shapely import make_valid
from shapely.errors import GEOSException
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

from renewable_planner.domain.common import SpatialGeometry
from renewable_planner.domain.crs import (
    CrsDefinition,
    NonMetricCoordinateReferenceSystemError,
)
from renewable_planner.ports.spatial import CoordinateReferenceSystemService

LOGGER = logging.getLogger(__name__)


class SpatialOperationError(ValueError):
    """Base error raised when a geometry operation cannot be completed."""


class InvalidSpatialGeometryError(SpatialOperationError):
    """Raised when an operation receives invalid or unreadable geometry."""


class CoordinateReferenceSystemMismatchError(SpatialOperationError):
    """Raised when geometries use different coordinate systems or units."""


class GeoPandasSpatialOperations:
    """Perform spatial operations while keeping GIS types inside the adapter."""

    def __init__(self, crs_service: CoordinateReferenceSystemService) -> None:
        self._crs_service = crs_service

    def is_valid(self, geometry: SpatialGeometry) -> bool:
        series = self._series(geometry)
        return bool(series.is_valid.iloc[0])

    def repair(self, geometry: SpatialGeometry) -> SpatialGeometry:
        series = self._series(geometry)
        source = series.iloc[0]
        if source.is_valid:
            return geometry

        reason = explain_validity(source)
        LOGGER.warning("Repairing invalid geometry: %s", reason)
        try:
            repaired = make_valid(source)
        except (GEOSException, ValueError) as error:
            raise InvalidSpatialGeometryError("geometry could not be repaired") from error
        if repaired.is_empty or not repaired.is_valid:
            raise InvalidSpatialGeometryError("geometry repair did not produce a valid result")
        return SpatialGeometry(wkt=repaired.wkt, crs=geometry.crs)

    def reproject(self, geometry: SpatialGeometry, target_crs: str) -> SpatialGeometry:
        self._definition(geometry)
        self._crs_service.inspect(target_crs)
        return self._crs_service.transform(geometry, target_crs)

    def buffer_meters(
        self,
        geometry: SpatialGeometry,
        distance_meters: float,
    ) -> SpatialGeometry:
        self._require_metric(self._definition(geometry))
        if distance_meters < 0:
            raise ValueError("distance_meters must not be negative")
        source = self._valid_series(geometry)
        buffered = source.buffer(distance_meters).iloc[0]
        return SpatialGeometry(wkt=buffered.wkt, crs=geometry.crs)

    def intersection(
        self,
        left: SpatialGeometry,
        right: SpatialGeometry,
    ) -> SpatialGeometry | None:
        self._require_compatible(left, right)
        left_series = self._valid_series(left)
        right_geometry = self._valid_series(right).iloc[0]
        result = left_series.intersection(right_geometry).iloc[0]
        return self._result(result, left.crs)

    def difference(
        self,
        left: SpatialGeometry,
        right: SpatialGeometry,
    ) -> SpatialGeometry | None:
        self._require_compatible(left, right)
        left_series = self._valid_series(left)
        right_geometry = self._valid_series(right).iloc[0]
        result = left_series.difference(right_geometry).iloc[0]
        return self._result(result, left.crs)

    def union(self, geometries: Sequence[SpatialGeometry]) -> SpatialGeometry | None:
        if not geometries:
            return None
        first = geometries[0]
        for geometry in geometries[1:]:
            self._require_compatible(first, geometry)
        series = geopandas.GeoSeries(
            [self._valid_series(geometry).iloc[0] for geometry in geometries],
            crs=first.crs,
        )
        return self._result(series.union_all(), first.crs)

    def intersects(self, left: SpatialGeometry, right: SpatialGeometry) -> bool:
        self._require_compatible(left, right)
        left_series = self._valid_series(left)
        right_geometry = self._valid_series(right).iloc[0]
        return bool(left_series.intersects(right_geometry).iloc[0])

    def area_square_meters(self, geometry: SpatialGeometry) -> float:
        self._require_metric(self._definition(geometry))
        return float(self._valid_series(geometry).area.iloc[0])

    def _series(self, geometry: SpatialGeometry) -> geopandas.GeoSeries:
        self._definition(geometry)
        try:
            return geopandas.GeoSeries.from_wkt([geometry.wkt], crs=geometry.crs)
        except (GEOSException, ValueError, TypeError) as error:
            raise InvalidSpatialGeometryError("geometry WKT cannot be read") from error

    def _valid_series(self, geometry: SpatialGeometry) -> geopandas.GeoSeries:
        series = self._series(geometry)
        source = series.iloc[0]
        if source.is_empty:
            raise InvalidSpatialGeometryError("geometry must not be empty")
        if not source.is_valid:
            reason = explain_validity(source)
            LOGGER.warning("Rejected invalid geometry: %s", reason)
            raise InvalidSpatialGeometryError(f"geometry is invalid: {reason}")
        return series

    def _definition(self, geometry: SpatialGeometry) -> CrsDefinition:
        return self._crs_service.inspect(geometry.crs)

    def _require_compatible(
        self,
        left: SpatialGeometry,
        right: SpatialGeometry,
    ) -> None:
        left_definition = self._definition(left)
        right_definition = self._definition(right)
        if (
            left_definition.identifier != right_definition.identifier
            or left_definition.axis_units != right_definition.axis_units
        ):
            raise CoordinateReferenceSystemMismatchError(
                "geometries must use the same CRS and units"
            )

    @staticmethod
    def _require_metric(definition: CrsDefinition) -> None:
        if not definition.is_metric:
            raise NonMetricCoordinateReferenceSystemError(
                f"CRS {definition.identifier} must use metric units"
            )

    @staticmethod
    def _result(geometry: BaseGeometry, crs: str) -> SpatialGeometry | None:
        if geometry.is_empty:
            return None
        return SpatialGeometry(wkt=geometry.wkt, crs=crs)
