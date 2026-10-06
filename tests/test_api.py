"""Tests for the FastAPI web interface (Step 1 — synchronous, in-memory)."""

from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.web
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from renewable_planner.api.app import app  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _upload_files() -> dict[str, tuple[str, bytes, str]]:
    return {
        "site": (
            "site.geojson",
            (FIXTURES / "cli_site.geojson").read_bytes(),
            "application/geo+json",
        ),
        "constraints": (
            "constraints.geojson",
            (FIXTURES / "cli_constraints.geojson").read_bytes(),
            "application/geo+json",
        ),
        "rules": (
            "rules.yaml",
            (FIXTURES / "cli_rules.yaml").read_bytes(),
            "application/x-yaml",
        ),
    }


def test_health_check(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_screening_returns_summary(client: TestClient) -> None:
    response = client.post(
        "/v1/screenings",
        files=_upload_files(),
        data={"technology": "wind", "analysis_date": "2026-08-17"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["initial_area_square_meters"] == pytest.approx(400.0)
    assert body["warnings"] == 1
    assert len(body["findings"]) == 2


def test_get_screening_returns_the_same_summary_later(client: TestClient) -> None:
    created = client.post(
        "/v1/screenings",
        files=_upload_files(),
        data={"technology": "wind", "analysis_date": "2026-08-17"},
    ).json()

    fetched = client.get(f"/v1/screenings/{created['id']}")

    assert fetched.status_code == 200
    assert fetched.json() == created


def test_get_unknown_screening_returns_404(client: TestClient) -> None:
    response = client.get(f"/v1/screenings/{uuid4()}")

    assert response.status_code == 404


def test_get_screening_report_renders_text(client: TestClient) -> None:
    created = client.post(
        "/v1/screenings",
        files=_upload_files(),
        data={"technology": "wind", "analysis_date": "2026-08-17"},
    ).json()

    report = client.get(f"/v1/screenings/{created['id']}/report")

    assert report.status_code == 200
    assert "RAPORT WSTĘPNEGO SCREENINGU TERENU" in report.text
    assert "nie jest wiążącą opinią prawną" in report.text


def test_get_screening_layers_returns_geojson(client: TestClient) -> None:
    created = client.post(
        "/v1/screenings",
        files=_upload_files(),
        data={"technology": "wind", "analysis_date": "2026-08-17"},
    ).json()

    available = client.get(f"/v1/screenings/{created['id']}/layers/available")
    excluded = client.get(f"/v1/screenings/{created['id']}/layers/excluded")

    assert available.status_code == 200
    assert available.json()["type"] == "FeatureCollection"
    assert excluded.status_code == 200
    assert excluded.json()["features"]


def _warsaw_area_upload_files() -> dict[str, tuple[str, bytes, str]]:
    """Like ``_upload_files``, but the site/constraints use real-looking
    EPSG:2180 coordinates (offset into the Warsaw area) instead of the
    (0, 0)-(20, 20) toy square the other fixtures use — needed to tell a
    reprojected-to-WGS84 coordinate apart from a raw, un-reprojected one by
    its magnitude (see the reprojection test below). Same topology as
    ``tests/fixtures/cli_site.geojson``/``cli_constraints.geojson``, just
    translated, so ``tests/fixtures/cli_rules.yaml`` still applies unchanged.
    """
    site = b"""
    {
      "type": "FeatureCollection",
      "crs": {"type": "name", "properties": {"name": "EPSG:2180"}},
      "features": [{
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [[
          [630000, 480000], [630020, 480000], [630020, 480020], [630000, 480020], [630000, 480000]
        ]]}
      }]
    }
    """
    constraints = b"""
    {
      "type": "FeatureCollection",
      "crs": {"type": "name", "properties": {"name": "EPSG:2180"}},
      "features": [
        {
          "type": "Feature",
          "properties": {"layer": "buildings", "source": "synthetic-buildings", "version": "v1"},
          "geometry": {"type": "Polygon", "coordinates": [[
            [630002, 480002], [630006, 480002], [630006, 480006], [630002, 480006], [630002, 480002]
          ]]}
        },
        {
          "type": "Feature",
          "properties": {
            "layer": "environment", "source": "synthetic-environment", "version": "v2"
          },
          "geometry": {"type": "Polygon", "coordinates": [[
            [630012, 480012], [630016, 480012], [630016, 480016], [630012, 480016], [630012, 480012]
          ]]}
        }
      ]
    }
    """
    return {
        "site": ("site.geojson", site, "application/geo+json"),
        "constraints": ("constraints.geojson", constraints, "application/geo+json"),
        "rules": (
            "rules.yaml",
            (FIXTURES / "cli_rules.yaml").read_bytes(),
            "application/x-yaml",
        ),
    }


def test_get_screening_layers_are_reprojected_to_wgs84_for_the_map(client: TestClient) -> None:
    """Layer geometries must be in WGS84 lon/lat, not the analysis CRS.

    The fixture site sits at real-looking EPSG:2180 (metres) coordinates in
    the Warsaw area — a web map (MapLibre) expects GeoJSON in EPSG:4326
    (degrees). Raw, un-reprojected coordinates (hundreds of thousands) would
    fail even the basic lon/lat range check, let alone land near Warsaw.
    """
    created = client.post(
        "/v1/screenings",
        files=_warsaw_area_upload_files(),
        data={"technology": "wind", "analysis_date": "2026-08-17"},
    ).json()

    excluded = client.get(f"/v1/screenings/{created['id']}/layers/excluded").json()

    def all_coordinates(geometry: dict) -> list[list[float]]:
        coordinates = geometry["coordinates"]
        while isinstance(coordinates[0][0], list):
            coordinates = [point for ring in coordinates for point in ring]
        return coordinates

    points = [
        point for feature in excluded["features"] for point in all_coordinates(feature["geometry"])
    ]
    assert points
    for longitude, latitude in points:
        # Warsaw's rough bounding box — reachable only via a real
        # reprojection, not by accident (raw EPSG:2180 values here are
        # ~630000/~480000, nowhere near valid lon/lat).
        assert 20.0 <= longitude <= 22.0
        assert 51.0 <= latitude <= 53.0


def test_get_unknown_layer_returns_404(client: TestClient) -> None:
    created = client.post(
        "/v1/screenings",
        files=_upload_files(),
        data={"technology": "wind", "analysis_date": "2026-08-17"},
    ).json()

    response = client.get(f"/v1/screenings/{created['id']}/layers/bogus")

    assert response.status_code == 404


def test_create_screening_rejects_empty_technology(client: TestClient) -> None:
    response = client.post(
        "/v1/screenings",
        files=_upload_files(),
        data={"technology": "   "},
    )

    assert response.status_code == 422


def test_create_screening_rejects_invalid_site_file(client: TestClient) -> None:
    files = _upload_files()
    files["site"] = ("site.geojson", b"not geojson", "application/geo+json")

    response = client.post(
        "/v1/screenings",
        files=files,
        data={"technology": "wind"},
    )

    assert response.status_code == 422
