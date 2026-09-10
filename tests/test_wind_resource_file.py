import json
from pathlib import Path

import pytest
import yaml

from renewable_planner.adapters.wind_resource import (
    WindResourceFileError,
    WindResourceFileProvider,
    load_wind_resource_time_series,
)
from renewable_planner.domain import WindResourceTimeSeries

FIXTURE = Path(__file__).parent / "fixtures" / "wind_resource_sample.yaml"

DOCUMENT = {
    "source": "Fikcyjna stacja pomiarowa testowa",
    "version": "test-v1",
    "records": [
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "wind_speed_mps": 4.0,
            "wind_direction_deg": 180.0,
        },
        {
            "timestamp": "2026-01-01T01:00:00+00:00",
            "wind_speed_mps": 6.5,
            "wind_direction_deg": 190.0,
        },
    ],
}


def test_loads_fixture_series() -> None:
    series = load_wind_resource_time_series(FIXTURE)

    assert isinstance(series, WindResourceTimeSeries)
    assert series.source == "Fikcyjna stacja pomiarowa testowa"
    assert series.version == "test-v1"
    assert len(series.samples) == 4
    assert series.wind_speeds_mps[0] == 4.0


@pytest.mark.parametrize("suffix", [".yaml", ".json"])
def test_loads_synthetic_series_from_yaml_or_json(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"wind{suffix}"
    if suffix == ".yaml":
        path.write_text(yaml.safe_dump(DOCUMENT), encoding="utf-8")
    else:
        path.write_text(json.dumps(DOCUMENT), encoding="utf-8")

    series = load_wind_resource_time_series(path)

    assert series.wind_speeds_mps == (4.0, 6.5)
    assert series.wind_directions_deg == (180.0, 190.0)


def test_provider_returns_the_loaded_series() -> None:
    provider = WindResourceFileProvider(FIXTURE)

    first = provider.get_time_series()
    second = provider.get_time_series()

    assert first is second
    assert first.source == "Fikcyjna stacja pomiarowa testowa"


def test_loader_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(WindResourceFileError, match="cannot read"):
        load_wind_resource_time_series(tmp_path / "missing.yaml")


def test_loader_reports_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("records: [\n", encoding="utf-8")

    with pytest.raises(WindResourceFileError, match="cannot parse"):
        load_wind_resource_time_series(path)


def test_loader_reports_unsupported_suffix(tmp_path: Path) -> None:
    path = tmp_path / "wind.txt"
    path.write_text("records: []", encoding="utf-8")

    with pytest.raises(WindResourceFileError, match="suffix"):
        load_wind_resource_time_series(path)


def test_loader_reports_missing_records_list(tmp_path: Path) -> None:
    path = tmp_path / "wind.yaml"
    path.write_text(yaml.safe_dump({"source": "s", "version": "v1"}), encoding="utf-8")

    with pytest.raises(WindResourceFileError, match="records"):
        load_wind_resource_time_series(path)


def test_loader_reports_empty_series(tmp_path: Path) -> None:
    path = tmp_path / "wind.yaml"
    document = dict(DOCUMENT, records=[])
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(WindResourceFileError, match="empty"):
        load_wind_resource_time_series(path)


def test_loader_reports_missing_source_or_version(tmp_path: Path) -> None:
    path = tmp_path / "wind.yaml"
    document = {k: v for k, v in DOCUMENT.items() if k != "source"}
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(WindResourceFileError, match="source"):
        load_wind_resource_time_series(path)


def test_loader_reports_invalid_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "wind.yaml"
    document = dict(DOCUMENT, records=[{**DOCUMENT["records"][0], "timestamp": "not-a-date"}])
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(WindResourceFileError, match="ISO-8601"):
        load_wind_resource_time_series(path)


def test_loader_reports_invalid_wind_speed(tmp_path: Path) -> None:
    path = tmp_path / "wind.yaml"
    document = dict(DOCUMENT, records=[{**DOCUMENT["records"][0], "wind_speed_mps": "fast"}])
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(WindResourceFileError, match="wind_speed_mps"):
        load_wind_resource_time_series(path)


def test_loader_reports_non_contiguous_records(tmp_path: Path) -> None:
    path = tmp_path / "wind.yaml"
    document = dict(
        DOCUMENT,
        records=[
            DOCUMENT["records"][0],
            {**DOCUMENT["records"][0], "timestamp": "2026-01-01T03:00:00+00:00"},
        ],
    )
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(WindResourceFileError, match="contiguous"):
        load_wind_resource_time_series(path)
