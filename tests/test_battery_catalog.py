import json
from pathlib import Path

import pytest
import yaml

from renewable_planner.adapters.battery_catalog import BatteryCatalogError, load_battery_catalog

BATTERY = {
    "manufacturer": "Fikcyjny Storage",
    "model_name": "FB-100",
    "capacity_mwh": 100.0,
    "max_charge_power_mw": 25.0,
    "max_discharge_power_mw": 25.0,
    "round_trip_efficiency_percent": 90.0,
    "min_state_of_charge_fraction": 0.1,
    "max_state_of_charge_fraction": 0.9,
    "data_source": "synthetic-test-dataset",
    "data_version": "2026-01",
}


@pytest.mark.parametrize("suffix", [".yaml", ".json"])
def test_loads_synthetic_catalog_from_yaml_or_json(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"batteries{suffix}"
    document = {"batteries": [BATTERY]}
    if suffix == ".yaml":
        path.write_text(yaml.safe_dump(document), encoding="utf-8")
    else:
        path.write_text(json.dumps(document), encoding="utf-8")

    catalog = load_battery_catalog(path)

    assert len(catalog.batteries) == 1
    assert catalog.batteries[0].capacity_mwh == 100.0
    assert catalog.batteries[0].data_source == "synthetic-test-dataset"


def test_loader_reports_invalid_field_and_unsupported_format(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.yaml"
    invalid_entry = dict(BATTERY, manufacturer="")
    invalid_path.write_text(yaml.safe_dump({"batteries": [invalid_entry]}), encoding="utf-8")

    with pytest.raises(BatteryCatalogError, match="manufacturer"):
        load_battery_catalog(invalid_path)

    unsupported_path = tmp_path / "batteries.txt"
    unsupported_path.write_text("batteries: []", encoding="utf-8")
    with pytest.raises(BatteryCatalogError, match="suffix"):
        load_battery_catalog(unsupported_path)


def test_loader_reports_missing_batteries_list(tmp_path: Path) -> None:
    path = tmp_path / "batteries.yaml"
    path.write_text(yaml.safe_dump({}), encoding="utf-8")

    with pytest.raises(BatteryCatalogError, match="batteries"):
        load_battery_catalog(path)
