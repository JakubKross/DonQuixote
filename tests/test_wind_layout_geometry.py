import pytest

from renewable_planner.adapters.geospatial import (
    AvailableAreaExtractionError,
    PyprojCoordinateReferenceSystemService,
    ShapelyAvailableAreaExtractor,
)
from renewable_planner.domain import NonMetricCoordinateReferenceSystemError, SpatialGeometry
from renewable_planner.ports import AvailableAreaExtractor

CRS = "EPSG:2180"


def _extractor() -> ShapelyAvailableAreaExtractor:
    return ShapelyAvailableAreaExtractor(PyprojCoordinateReferenceSystemService())


def test_adapter_implements_available_area_extractor_port() -> None:
    assert isinstance(_extractor(), AvailableAreaExtractor)


def test_extracts_square_polygon_without_duplicated_closing_point() -> None:
    geometry = SpatialGeometry(
        "POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0))",
        CRS,
    )

    area = _extractor().extract(geometry)

    assert area.exterior == ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    assert area.holes == ()


def test_extracts_polygon_with_hole() -> None:
    geometry = SpatialGeometry(
        "POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0), (40 40, 60 40, 60 60, 40 60, 40 40))",
        CRS,
    )

    area = _extractor().extract(geometry)

    assert area.holes == (((40.0, 40.0), (60.0, 40.0), (60.0, 60.0), (40.0, 60.0)),)


def test_rejects_multipolygon() -> None:
    geometry = SpatialGeometry(
        "MULTIPOLYGON (((0 0, 10 0, 10 10, 0 10, 0 0)), ((20 20, 30 20, 30 30, 20 30, 20 20)))",
        CRS,
    )

    with pytest.raises(AvailableAreaExtractionError, match="disjoint"):
        _extractor().extract(geometry)


def test_accepts_multipolygon_with_a_single_non_empty_part() -> None:
    geometry = SpatialGeometry(
        "MULTIPOLYGON (((0 0, 10 0, 10 10, 0 10, 0 0)))",
        CRS,
    )

    area = _extractor().extract(geometry)

    assert area.exterior == ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))


def test_rejects_empty_geometry() -> None:
    geometry = SpatialGeometry("POLYGON EMPTY", CRS)

    with pytest.raises(AvailableAreaExtractionError, match="empty"):
        _extractor().extract(geometry)


def test_rejects_non_polygon_geometry() -> None:
    geometry = SpatialGeometry("LINESTRING (0 0, 10 10)", CRS)

    with pytest.raises(AvailableAreaExtractionError, match="polygon"):
        _extractor().extract(geometry)


def test_rejects_invalid_wkt() -> None:
    geometry = SpatialGeometry("NOT WKT", CRS)

    with pytest.raises(AvailableAreaExtractionError, match="WKT"):
        _extractor().extract(geometry)


def test_rejects_geographic_crs() -> None:
    geometry = SpatialGeometry("POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))", "EPSG:4326")

    with pytest.raises(NonMetricCoordinateReferenceSystemError, match="geographic"):
        _extractor().extract(geometry)
