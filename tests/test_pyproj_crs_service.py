import pytest

from renewable_planner.adapters.geospatial import (
    PyprojCoordinateReferenceSystemService,
)
from renewable_planner.domain import (
    MissingCoordinateReferenceSystemError,
    SpatialGeometry,
    UnrecognizedCoordinateReferenceSystemError,
)
from renewable_planner.ports import CoordinateReferenceSystemService


def test_pyproj_adapter_implements_crs_service_port() -> None:
    service = PyprojCoordinateReferenceSystemService()

    assert isinstance(service, CoordinateReferenceSystemService)


def test_epsg_4326_is_recognized_as_geographic() -> None:
    definition = PyprojCoordinateReferenceSystemService().inspect("EPSG:4326")

    assert definition.identifier == "EPSG:4326"
    assert definition.is_geographic
    assert not definition.is_metric


def test_epsg_2180_is_recognized_as_metric() -> None:
    definition = PyprojCoordinateReferenceSystemService().inspect("EPSG:2180")

    assert definition.identifier == "EPSG:2180"
    assert not definition.is_geographic
    assert definition.is_metric


@pytest.mark.parametrize("crs", [None, ""])
def test_missing_crs_is_rejected(crs: str | None) -> None:
    with pytest.raises(MissingCoordinateReferenceSystemError):
        PyprojCoordinateReferenceSystemService().inspect(crs)


def test_unknown_epsg_code_is_rejected() -> None:
    with pytest.raises(UnrecognizedCoordinateReferenceSystemError):
        PyprojCoordinateReferenceSystemService().inspect("EPSG:999999")


def test_geometry_is_transformed_between_coordinate_systems() -> None:
    service = PyprojCoordinateReferenceSystemService()
    geometry = SpatialGeometry("POINT (19 52)", "EPSG:4326")

    transformed = service.transform(geometry, "EPSG:2180")

    assert transformed.crs == "EPSG:2180"
    assert transformed.wkt != geometry.wkt
    assert transformed.wkt.startswith("POINT")
