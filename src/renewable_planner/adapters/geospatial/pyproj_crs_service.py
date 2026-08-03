"""PyProj and Shapely adapter for coordinate-system operations."""

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError, ProjError
from shapely import wkt
from shapely.errors import GEOSException
from shapely.ops import transform as transform_geometry

from renewable_planner.domain.common import SpatialGeometry
from renewable_planner.domain.crs import (
    CoordinateTransformationError,
    CrsDefinition,
    MissingCoordinateReferenceSystemError,
    UnrecognizedCoordinateReferenceSystemError,
)


class PyprojCoordinateReferenceSystemService:
    """Resolve CRS metadata and transform WKT geometries."""

    def inspect(self, crs: str | None) -> CrsDefinition:
        """Resolve a CRS using the PROJ database."""
        if crs is None or not crs.strip():
            raise MissingCoordinateReferenceSystemError("spatial data has no CRS")

        try:
            definition = CRS.from_user_input(crs)
        except CRSError as error:
            raise UnrecognizedCoordinateReferenceSystemError(
                f"cannot recognize CRS: {crs}"
            ) from error

        authority = definition.to_authority()
        if authority is None or authority[0].upper() != "EPSG":
            raise UnrecognizedCoordinateReferenceSystemError(
                f"CRS has no recognized EPSG identifier: {crs}"
            )

        return CrsDefinition(
            identifier=f"EPSG:{authority[1]}",
            is_geographic=definition.is_geographic,
            axis_units=tuple(axis.unit_name or "" for axis in definition.axis_info),
        )

    def transform(
        self,
        geometry: SpatialGeometry,
        target_crs: str,
    ) -> SpatialGeometry:
        """Transform domain geometry without leaking PyProj or Shapely objects."""
        source = self.inspect(geometry.crs)
        target = self.inspect(target_crs)
        if source.identifier == target.identifier:
            return geometry

        try:
            shapely_geometry = wkt.loads(geometry.wkt)
            transformer = Transformer.from_crs(
                source.identifier,
                target.identifier,
                always_xy=True,
            )
            transformed = transform_geometry(
                transformer.transform,
                shapely_geometry,
            )
        except (CRSError, ProjError, GEOSException, ValueError) as error:
            raise CoordinateTransformationError(
                f"cannot transform geometry from {source.identifier} to {target.identifier}"
            ) from error

        return SpatialGeometry(wkt=transformed.wkt, crs=target.identifier)
