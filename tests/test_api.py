"""Tests for the FastAPI web interface (Step 1 — synchronous, in-memory)."""

from pathlib import Path
from typing import Any
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


def _create_screening(client: TestClient) -> str:
    response = client.post(
        "/v1/screenings",
        files=_upload_files(),
        data={"technology": "wind", "analysis_date": "2026-08-17"},
    )
    assert response.status_code == 201
    screening_id: str = response.json()["id"]
    return screening_id


def _fixture_upload(name: str) -> tuple[str, bytes, str]:
    return (name, (FIXTURES / name).read_bytes(), "application/x-yaml")


def _post_wind(client: TestClient, screening_id: str, *, with_resource: bool = True) -> Any:
    files = {"turbine_catalog": _fixture_upload("cli_turbine_catalog.yaml")}
    if with_resource:
        files["wind_resource"] = _fixture_upload("wind_resource_sample.yaml")
    return client.post(
        f"/v1/screenings/{screening_id}/turbine-layout",
        files=files,
        data={"spacing_rotor_diameters": "3"},
    )


def test_list_screenings_returns_newest_first(client: TestClient) -> None:
    first = _create_screening(client)
    second = _create_screening(client)

    response = client.get("/v1/screenings", params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [second, first]
    assert body[0]["status"] == "completed"
    assert body[0]["created_at"] is not None


def test_list_screenings_rejects_out_of_range_limit(client: TestClient) -> None:
    assert client.get("/v1/screenings", params={"limit": 0}).status_code == 422


def test_turbine_layout_places_turbines_and_simulates_production(client: TestClient) -> None:
    screening_id = _create_screening(client)

    response = _post_wind(client, screening_id)

    assert response.status_code == 200
    body = response.json()
    assert body["turbine_model"] == "FW-Test"
    assert body["turbine_count"] == len(body["positions"]) > 0
    assert body["crs"] == "EPSG:2180"
    simulation = body["simulation"]
    assert simulation["simulator"] == "simple"
    assert simulation["wake_energy_mwh"] > 0
    assert len(simulation["wake_profile"]["power_mw"]) == len(
        simulation["wake_profile"]["timestamps"]
    )


def test_turbine_layout_without_resource_skips_simulation(client: TestClient) -> None:
    screening_id = _create_screening(client)

    response = _post_wind(client, screening_id, with_resource=False)

    assert response.status_code == 200
    assert response.json()["simulation"] is None


def test_turbine_layout_rejects_unknown_turbine(client: TestClient) -> None:
    screening_id = _create_screening(client)

    response = client.post(
        f"/v1/screenings/{screening_id}/turbine-layout",
        files={"turbine_catalog": _fixture_upload("cli_turbine_catalog.yaml")},
        data={
            "spacing_rotor_diameters": "3",
            "turbine_manufacturer": "Nieznany",
            "turbine_model": "X",
        },
    )

    assert response.status_code == 422
    assert "not found in catalog" in response.json()["detail"]


def test_technology_endpoints_return_404_for_unknown_screening(client: TestClient) -> None:
    unknown = uuid4()

    assert client.get(f"/v1/screenings/{unknown}/technologies").status_code == 404
    assert _post_wind(client, str(unknown)).status_code == 404


def test_solar_array_sizes_and_simulates(client: TestClient) -> None:
    screening_id = _create_screening(client)

    response = client.post(
        f"/v1/screenings/{screening_id}/solar-array",
        files={
            "solar_catalog": _fixture_upload("cli_solar_catalog.yaml"),
            "solar_resource": _fixture_upload("solar_resource_sample.yaml"),
        },
        data={"ground_coverage_ratio": "0.5"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["module_count"] > 0
    assert body["installed_capacity_kwp"] == pytest.approx(body["module_count"] * 0.4)
    assert body["simulation"]["ac_energy_mwh"] > 0


def test_hybrid_requires_a_production_simulation(client: TestClient) -> None:
    screening_id = _create_screening(client)
    _post_wind(client, screening_id, with_resource=False)

    response = client.post(
        f"/v1/screenings/{screening_id}/hybrid", data={"grid_connection_limit_mw": "1"}
    )

    assert response.status_code == 409


def test_battery_dispatch_requires_a_hybrid_result(client: TestClient) -> None:
    screening_id = _create_screening(client)

    response = client.post(
        f"/v1/screenings/{screening_id}/battery-dispatch",
        files={"battery_catalog": _fixture_upload("cli_battery_catalog.yaml")},
    )

    assert response.status_code == 409


def test_wind_hybrid_battery_chain_is_stored_and_rerun_clears_derived_results(
    client: TestClient,
) -> None:
    screening_id = _create_screening(client)
    wind = _post_wind(client, screening_id).json()
    # Low enough to force curtailment, so the battery has surplus to absorb.
    limit_mw = max(wind["simulation"]["wake_profile"]["power_mw"]) / 2

    hybrid = client.post(
        f"/v1/screenings/{screening_id}/hybrid",
        data={"grid_connection_limit_mw": str(limit_mw)},
    )
    assert hybrid.status_code == 200
    assert hybrid.json()["sources"] == ["wind"]
    assert hybrid.json()["curtailed_energy_mwh"] > 0

    battery = client.post(
        f"/v1/screenings/{screening_id}/battery-dispatch",
        files={"battery_catalog": _fixture_upload("cli_battery_catalog.yaml")},
    )
    assert battery.status_code == 200
    assert battery.json()["target_power_mw"] == pytest.approx(limit_mw)
    assert battery.json()["charged_energy_mwh"] > 0

    stored = client.get(f"/v1/screenings/{screening_id}/technologies").json()
    assert stored["wind"] == wind
    assert stored["solar"] is None
    assert stored["hybrid"] == hybrid.json()
    assert stored["battery"] == battery.json()

    _post_wind(client, screening_id)
    after_rerun = client.get(f"/v1/screenings/{screening_id}/technologies").json()
    assert after_rerun["wind"] is not None
    assert after_rerun["hybrid"] is None
    assert after_rerun["battery"] is None
