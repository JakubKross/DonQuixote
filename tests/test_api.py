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
