"""Spatial infrastructure adapters."""

from renewable_planner.adapters.geospatial.geojson_site_boundary import (
    BoundaryFileNotConfiguredError,
    BoundaryFileNotFoundError,
    EmptyBoundaryLayerError,
    GeoJsonBoundaryError,
    GeoJsonSiteBoundaryProvider,
    InvalidBoundaryGeometryError,
    InvalidGeoJsonError,
    MissingBoundaryGeometryError,
    MissingCrsError,
    MultipleBoundaryGeometriesError,
    UnsupportedCrsError,
)
from renewable_planner.adapters.geospatial.geopandas_spatial_operations import (
    CoordinateReferenceSystemMismatchError,
    GeoPandasSpatialOperations,
    InvalidSpatialGeometryError,
    SpatialOperationError,
)
from renewable_planner.adapters.geospatial.pyproj_crs_service import (
    PyprojCoordinateReferenceSystemService,
)

__all__ = [
    "BoundaryFileNotConfiguredError",
    "BoundaryFileNotFoundError",
    "CoordinateReferenceSystemMismatchError",
    "EmptyBoundaryLayerError",
    "GeoJsonBoundaryError",
    "GeoJsonSiteBoundaryProvider",
    "GeoPandasSpatialOperations",
    "InvalidBoundaryGeometryError",
    "InvalidGeoJsonError",
    "InvalidSpatialGeometryError",
    "MissingBoundaryGeometryError",
    "MissingCrsError",
    "MultipleBoundaryGeometriesError",
    "PyprojCoordinateReferenceSystemService",
    "SpatialOperationError",
    "UnsupportedCrsError",
]
