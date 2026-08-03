"""GeoJSON adapter for site boundaries."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from uuid import UUID

import geopandas

from renewable_planner.domain.common import SpatialGeometry


class GeoJsonBoundaryError(ValueError):
    """Base error raised when a GeoJSON boundary cannot be loaded."""


class BoundaryFileNotConfiguredError(GeoJsonBoundaryError):
    """Raised when no file is configured for a site."""


class BoundaryFileNotFoundError(GeoJsonBoundaryError, FileNotFoundError):
    """Raised when the configured boundary file does not exist."""


class InvalidGeoJsonError(GeoJsonBoundaryError):
    """Raised when a file is not valid JSON or readable GeoJSON."""


class EmptyBoundaryLayerError(GeoJsonBoundaryError):
    """Raised when a boundary layer contains no features."""


class MissingBoundaryGeometryError(GeoJsonBoundaryError):
    """Raised when the single feature has no geometry."""


class MultipleBoundaryGeometriesError(GeoJsonBoundaryError):
    """Raised when a boundary layer has more than one feature."""


class InvalidBoundaryGeometryError(GeoJsonBoundaryError):
    """Raised when the boundary geometry is empty or topologically invalid."""


class MissingCrsError(GeoJsonBoundaryError):
    """Raised when a boundary file does not declare a CRS."""


class UnsupportedCrsError(GeoJsonBoundaryError):
    """Raised when a declared CRS has no EPSG identifier."""


class GeoJsonSiteBoundaryProvider:
    """Load one site boundary feature from a configured GeoJSON file."""

    def __init__(self, boundary_files: Mapping[UUID, Path]) -> None:
        self._boundary_files = dict(boundary_files)

    def get_boundary(self, site_id: UUID) -> SpatialGeometry:
        """Load and validate the boundary configured for ``site_id``."""
        try:
            path = self._boundary_files[site_id]
        except KeyError as error:
            raise BoundaryFileNotConfiguredError(
                f"no boundary file configured for site {site_id}"
            ) from error

        document = self._read_json(path)
        if not self._declares_crs(document):
            raise MissingCrsError(f"boundary file does not declare a CRS: {path}")

        frame = self._read_geojson(path)
        if frame.empty:
            raise EmptyBoundaryLayerError(f"boundary layer is empty: {path}")
        if len(frame.index) > 1:
            raise MultipleBoundaryGeometriesError(
                f"boundary layer must contain exactly one feature: {path}"
            )
        if "geometry" not in frame.columns:
            raise MissingBoundaryGeometryError(f"boundary feature has no geometry: {path}")

        geometry = frame.geometry.iloc[0]
        if geometry is None:
            raise MissingBoundaryGeometryError(f"boundary feature has no geometry: {path}")
        if geometry.is_empty:
            raise InvalidBoundaryGeometryError(f"boundary geometry is empty: {path}")
        if not geometry.is_valid:
            raise InvalidBoundaryGeometryError(f"boundary geometry is invalid: {path}")
        if frame.crs is None:
            raise MissingCrsError(f"boundary layer has no readable CRS: {path}")

        authority = frame.crs.to_authority()
        if authority is None or authority[0].upper() != "EPSG":
            raise UnsupportedCrsError(f"boundary CRS must have an EPSG identifier: {frame.crs}")

        return SpatialGeometry(
            wkt=cast(str, geometry.wkt),
            crs=f"EPSG:{authority[1]}",
        )

    @staticmethod
    def _read_json(path: Path) -> object:
        if not path.is_file():
            raise BoundaryFileNotFoundError(f"boundary file does not exist: {path}")
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
            raise InvalidGeoJsonError(f"cannot parse boundary JSON: {path}") from error

    @staticmethod
    def _declares_crs(document: object) -> bool:
        return isinstance(document, dict) and "crs" in document and document["crs"] is not None

    @staticmethod
    def _read_geojson(path: Path) -> geopandas.GeoDataFrame:
        try:
            return geopandas.read_file(path)
        except Exception as error:
            raise InvalidGeoJsonError(f"cannot read boundary as GeoJSON: {path}") from error
