import pytest

from renewable_planner.domain import CrsValidationError, Site, SpatialGeometry


def test_site_keeps_library_neutral_boundary() -> None:
    boundary = SpatialGeometry(wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))", crs="EPSG:2180")

    site = Site(name="Obszar A", boundary=boundary)

    assert site.boundary.crs == "EPSG:2180"


@pytest.mark.parametrize("wkt, crs", [("", "EPSG:2180"), ("POINT (0 0)", "")])
def test_geometry_requires_wkt_and_crs(wkt: str, crs: str) -> None:
    with pytest.raises(ValueError):
        SpatialGeometry(wkt=wkt, crs=crs)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("EPSG:2180", "EPSG:2180"),
        ("epsg:4326", "EPSG:4326"),
        ("  EPSG : 3857  ", "EPSG:3857"),
    ],
)
def test_imported_geometry_normalizes_epsg_crs(source: str, expected: str) -> None:
    geometry = SpatialGeometry(wkt="POINT (0 0)", crs=source)

    assert geometry.crs == expected


@pytest.mark.parametrize(
    "crs",
    [
        "2180",
        "urn:ogc:def:crs:EPSG::2180",
        "CRS84",
        "EPSG:0",
        "EPSG:-2180",
        "EPSG:1000000",
        "EPSG:abc",
    ],
)
def test_imported_geometry_rejects_invalid_or_ambiguous_crs(crs: str) -> None:
    with pytest.raises(CrsValidationError):
        SpatialGeometry(wkt="POINT (0 0)", crs=crs)
