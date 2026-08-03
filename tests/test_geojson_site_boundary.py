import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from renewable_planner.adapters.geospatial import (
    BoundaryFileNotFoundError,
    EmptyBoundaryLayerError,
    GeoJsonSiteBoundaryProvider,
    InvalidBoundaryGeometryError,
    InvalidGeoJsonError,
    MissingBoundaryGeometryError,
    MissingCrsError,
    MultipleBoundaryGeometriesError,
)
from renewable_planner.domain import SpatialGeometry
from renewable_planner.ports import SiteBoundaryProvider

FIXTURES = Path(__file__).parent / "fixtures"


def _feature(geometry: object) -> dict[str, object]:
    return {
        "type": "Feature",
        "properties": {},
        "geometry": geometry,
    }


def _polygon(coordinates: list[list[list[float]]] | None = None) -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": coordinates or [[[19.0, 52.0], [19.1, 52.0], [19.1, 52.1], [19.0, 52.0]]],
    }


def _collection(features: list[dict[str, object]], include_crs: bool = True) -> dict[str, object]:
    document: dict[str, object] = {
        "type": "FeatureCollection",
        "features": features,
    }
    if include_crs:
        document["crs"] = {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:EPSG::4326"},
        }
    return document


def _write_geojson(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _provider(path: Path) -> tuple[GeoJsonSiteBoundaryProvider, UUID]:
    site_id = uuid4()
    return GeoJsonSiteBoundaryProvider({site_id: path}), site_id


def test_adapter_implements_site_boundary_port() -> None:
    provider, _ = _provider(FIXTURES / "site_boundary.geojson")

    assert isinstance(provider, SiteBoundaryProvider)


def test_integration_reads_fixture_without_leaking_gis_types() -> None:
    site_id = uuid4()
    provider = GeoJsonSiteBoundaryProvider({site_id: FIXTURES / "site_boundary.geojson"})

    boundary = provider.get_boundary(site_id)

    assert type(boundary) is SpatialGeometry
    assert boundary.crs == "EPSG:4326"
    assert boundary.wkt.startswith("POLYGON")


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    provider, site_id = _provider(tmp_path / "missing.geojson")

    with pytest.raises(BoundaryFileNotFoundError):
        provider.get_boundary(site_id)


def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "invalid.geojson"
    path.write_text("{invalid", encoding="utf-8")
    provider, site_id = _provider(path)

    with pytest.raises(InvalidGeoJsonError):
        provider.get_boundary(site_id)


def test_empty_layer_is_rejected(tmp_path: Path) -> None:
    path = _write_geojson(tmp_path / "empty.geojson", _collection([]))
    provider, site_id = _provider(path)

    with pytest.raises(EmptyBoundaryLayerError):
        provider.get_boundary(site_id)


def test_missing_geometry_is_rejected(tmp_path: Path) -> None:
    path = _write_geojson(
        tmp_path / "missing_geometry.geojson",
        _collection([_feature(None)]),
    )
    provider, site_id = _provider(path)

    with pytest.raises(MissingBoundaryGeometryError):
        provider.get_boundary(site_id)


def test_multiple_geometries_are_rejected(tmp_path: Path) -> None:
    path = _write_geojson(
        tmp_path / "multiple.geojson",
        _collection([_feature(_polygon()), _feature(_polygon())]),
    )
    provider, site_id = _provider(path)

    with pytest.raises(MultipleBoundaryGeometriesError):
        provider.get_boundary(site_id)


def test_invalid_geometry_is_rejected(tmp_path: Path) -> None:
    bow_tie = _polygon([[[0.0, 0.0], [1.0, 1.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]])
    path = _write_geojson(
        tmp_path / "invalid_geometry.geojson",
        _collection([_feature(bow_tie)]),
    )
    provider, site_id = _provider(path)

    with pytest.raises(InvalidBoundaryGeometryError):
        provider.get_boundary(site_id)


def test_missing_crs_is_rejected(tmp_path: Path) -> None:
    path = _write_geojson(
        tmp_path / "missing_crs.geojson",
        _collection([_feature(_polygon())], include_crs=False),
    )
    provider, site_id = _provider(path)

    with pytest.raises(MissingCrsError):
        provider.get_boundary(site_id)
