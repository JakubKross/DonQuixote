import json
from pathlib import Path

import pytest
import yaml

from renewable_planner.adapters.solar_resource import (
    SolarResourceFileError,
    SolarResourceFileProvider,
    load_solar_resource_time_series,
)
from renewable_planner.domain import SolarResourceTimeSeries

FIXTURE = Path(__file__).parent / "fixtures" / "solar_resource_sample.yaml"

DOCUMENT = {
    "source": "Fikcyjna stacja pomiarowa testowa",
    "version": "test-v1",
    "records": [
        {
            "timestamp": "2026-06-01T08:00:00+00:00",
            "poa_irradiance_w_per_m2": 200.0,
            "ambient_temperature_c": 15.0,
        },
        {
            "timestamp": "2026-06-01T09:00:00+00:00",
            "poa_irradiance_w_per_m2": 500.0,
            "ambient_temperature_c": 18.0,
        },
    ],
}


def test_loads_fixture_series() -> None:
    series = load_solar_resource_time_series(FIXTURE)

    assert isinstance(series, SolarResourceTimeSeries)
    assert series.source == "Fikcyjna stacja pomiarowa testowa"
    assert series.version == "test-v1"
    assert len(series.samples) == 4
    assert series.poa_irradiance_w_per_m2[0] == 200.0


@pytest.mark.parametrize("suffix", [".yaml", ".json"])
def test_loads_synthetic_series_from_yaml_or_json(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"solar{suffix}"
    if suffix == ".yaml":
        path.write_text(yaml.safe_dump(DOCUMENT), encoding="utf-8")
    else:
        path.write_text(json.dumps(DOCUMENT), encoding="utf-8")

    series = load_solar_resource_time_series(path)

    assert series.poa_irradiance_w_per_m2 == (200.0, 500.0)
    assert series.ambient_temperature_c == (15.0, 18.0)


def test_provider_returns_the_loaded_series() -> None:
    provider = SolarResourceFileProvider(FIXTURE)

    first = provider.get_time_series()
    second = provider.get_time_series()

    assert first is second
    assert first.source == "Fikcyjna stacja pomiarowa testowa"


def test_loader_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SolarResourceFileError, match="cannot read"):
        load_solar_resource_time_series(tmp_path / "missing.yaml")


def test_loader_reports_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("records: [\n", encoding="utf-8")

    with pytest.raises(SolarResourceFileError, match="cannot parse"):
        load_solar_resource_time_series(path)


def test_loader_reports_unsupported_suffix(tmp_path: Path) -> None:
    path = tmp_path / "solar.txt"
    path.write_text("records: []", encoding="utf-8")

    with pytest.raises(SolarResourceFileError, match="suffix"):
        load_solar_resource_time_series(path)


def test_loader_reports_missing_records_list(tmp_path: Path) -> None:
    path = tmp_path / "solar.yaml"
    path.write_text(yaml.safe_dump({"source": "s", "version": "v1"}), encoding="utf-8")

    with pytest.raises(SolarResourceFileError, match="records"):
        load_solar_resource_time_series(path)


def test_loader_reports_empty_series(tmp_path: Path) -> None:
    path = tmp_path / "solar.yaml"
    document = dict(DOCUMENT, records=[])
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(SolarResourceFileError, match="empty"):
        load_solar_resource_time_series(path)


def test_loader_reports_missing_source_or_version(tmp_path: Path) -> None:
    path = tmp_path / "solar.yaml"
    document = {k: v for k, v in DOCUMENT.items() if k != "source"}
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(SolarResourceFileError, match="source"):
        load_solar_resource_time_series(path)


def test_loader_reports_invalid_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "solar.yaml"
    document = dict(DOCUMENT, records=[{**DOCUMENT["records"][0], "timestamp": "not-a-date"}])
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(SolarResourceFileError, match="ISO-8601"):
        load_solar_resource_time_series(path)


def test_loader_reports_invalid_irradiance(tmp_path: Path) -> None:
    path = tmp_path / "solar.yaml"
    document = dict(
        DOCUMENT, records=[{**DOCUMENT["records"][0], "poa_irradiance_w_per_m2": "bright"}]
    )
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(SolarResourceFileError, match="poa_irradiance_w_per_m2"):
        load_solar_resource_time_series(path)


def test_loader_reports_non_contiguous_records(tmp_path: Path) -> None:
    path = tmp_path / "solar.yaml"
    document = dict(
        DOCUMENT,
        records=[
            DOCUMENT["records"][0],
            {**DOCUMENT["records"][0], "timestamp": "2026-06-01T11:00:00+00:00"},
        ],
    )
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(SolarResourceFileError, match="contiguous"):
        load_solar_resource_time_series(path)
