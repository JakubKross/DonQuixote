import logging
import math

import pytest

from renewable_planner.adapters.geospatial import (
    CoordinateReferenceSystemMismatchError,
    GeoPandasSpatialOperations,
    InvalidSpatialGeometryError,
    PyprojCoordinateReferenceSystemService,
)
from renewable_planner.domain import (
    NonMetricCoordinateReferenceSystemError,
    SpatialGeometry,
)
from renewable_planner.ports import SpatialOperations

CRS = "EPSG:2180"


def _operations() -> GeoPandasSpatialOperations:
    return GeoPandasSpatialOperations(PyprojCoordinateReferenceSystemService())


def _square(x_min: float, y_min: float, size: float) -> SpatialGeometry:
    x_max = x_min + size
    y_max = y_min + size
    return SpatialGeometry(
        f"POLYGON (({x_min} {y_min}, {x_max} {y_min}, {x_max} {y_max}, "
        f"{x_min} {y_max}, {x_min} {y_min}))",
        CRS,
    )


def test_adapter_implements_spatial_operations_port() -> None:
    assert isinstance(_operations(), SpatialOperations)


def test_no_intersection_returns_none_and_false() -> None:
    operations = _operations()
    left = _square(0, 0, 10)
    right = _square(20, 20, 10)

    assert not operations.intersects(left, right)
    assert operations.intersection(left, right) is None


def test_full_intersection_returns_the_full_area() -> None:
    operations = _operations()
    outer = _square(0, 0, 10)
    inner = _square(2, 2, 4)

    result = operations.intersection(outer, inner)

    assert result is not None
    assert operations.area_square_meters(result) == pytest.approx(16.0)


def test_partial_intersection_has_manually_verifiable_area() -> None:
    operations = _operations()
    left = _square(0, 0, 10)
    right = _square(5, 0, 10)

    result = operations.intersection(left, right)

    assert result is not None
    assert operations.area_square_meters(result) == pytest.approx(50.0)


def test_buffer_around_point_uses_metric_distance() -> None:
    operations = _operations()
    point = SpatialGeometry("POINT (0 0)", CRS)

    result = operations.buffer_meters(point, 100)

    assert operations.area_square_meters(result) == pytest.approx(
        math.pi * 100**2,
        rel=0.002,
    )


def test_difference_of_two_polygons_has_expected_area() -> None:
    operations = _operations()

    result = operations.difference(_square(0, 0, 10), _square(5, 0, 10))

    assert result is not None
    assert operations.area_square_meters(result) == pytest.approx(50.0)


def test_union_combines_polygons() -> None:
    operations = _operations()

    result = operations.union([_square(0, 0, 10), _square(5, 0, 10)])

    assert result is not None
    assert operations.area_square_meters(result) == pytest.approx(150.0)


def test_invalid_geometry_is_detected_rejected_and_repaired_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    operations = _operations()
    bow_tie = SpatialGeometry("POLYGON ((0 0, 2 2, 2 0, 0 2, 0 0))", CRS)

    assert not operations.is_valid(bow_tie)
    with caplog.at_level(logging.WARNING):
        repaired = operations.repair(bow_tie)

    assert operations.is_valid(repaired)
    assert "Repairing invalid geometry" in caplog.text
    with pytest.raises(InvalidSpatialGeometryError):
        operations.area_square_meters(bow_tie)


def test_binary_operation_rejects_different_crs() -> None:
    operations = _operations()
    geographic = SpatialGeometry("POINT (19 52)", "EPSG:4326")

    with pytest.raises(CoordinateReferenceSystemMismatchError):
        operations.intersects(SpatialGeometry("POINT (0 0)", CRS), geographic)


def test_metric_operation_rejects_angular_units() -> None:
    operations = _operations()
    geographic = SpatialGeometry("POLYGON ((19 52, 20 52, 20 53, 19 52))", "EPSG:4326")

    with pytest.raises(NonMetricCoordinateReferenceSystemError):
        operations.area_square_meters(geographic)
