"""Spatial infrastructure adapters."""

from renewable_planner.adapters.geospatial.file_screening import (
    FileProjectRepository,
    FileScreeningError,
    FileSiteRepository,
    GeoJsonConstraintLayerProvider,
    JsonResultRepository,
    MemoryAnalysisRunRepository,
    YamlSpatialRuleProvider,
    build_project,
    load_site,
    write_screening_outputs,
)
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
    "FileProjectRepository",
    "FileScreeningError",
    "FileSiteRepository",
    "GeoJsonConstraintLayerProvider",
    "EmptyBoundaryLayerError",
    "GeoJsonBoundaryError",
    "GeoJsonSiteBoundaryProvider",
    "GeoPandasSpatialOperations",
    "InvalidBoundaryGeometryError",
    "InvalidGeoJsonError",
    "InvalidSpatialGeometryError",
    "JsonResultRepository",
    "MemoryAnalysisRunRepository",
    "MissingBoundaryGeometryError",
    "MissingCrsError",
    "MultipleBoundaryGeometriesError",
    "PyprojCoordinateReferenceSystemService",
    "SpatialOperationError",
    "UnsupportedCrsError",
    "YamlSpatialRuleProvider",
    "build_project",
    "load_site",
    "write_screening_outputs",
]
