import json
from pathlib import Path

import pytest
import yaml

from renewable_planner.adapters.solar_catalog import (
    SolarModuleCatalogError,
    load_solar_module_catalog,
)
from renewable_planner.domain import SolarModule, SolarModuleCatalog, SolarModuleValidationError

MODULE = {
    "manufacturer": "Fikcyjny Solar",
    "model_name": "FS-400",
    "rated_power_w": 400,
    "width_m": 1.0,
    "height_m": 1.7,
    "temperature_coefficient_pct_per_c": -0.35,
    "data_source": "synthetic-test-dataset",
    "data_version": "2026-01",
}


def test_domain_model_accepts_valid_module_and_catalog_lookup() -> None:
    module = SolarModule(**MODULE)
    catalog = SolarModuleCatalog((module,))

    assert catalog.find("fikcyjny solar", "fs-400") is module
    assert module.area_m2 == pytest.approx(1.7)
    assert module.efficiency_percent == pytest.approx(400 / (1.7 * 1000) * 100)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("rated_power_w", 0, "greater than zero"),
        ("width_m", -1, "greater than zero"),
        ("height_m", float("inf"), "finite"),
        ("temperature_coefficient_pct_per_c", float("nan"), "finite"),
    ],
)
def test_domain_model_rejects_invalid_units_or_values(
    field: str, value: float, message: str
) -> None:
    values = dict(MODULE)
    values[field] = value

    with pytest.raises(SolarModuleValidationError, match=message):
        SolarModule(**values)


def test_domain_model_rejects_physically_impossible_efficiency() -> None:
    values = dict(MODULE, rated_power_w=5000)  # 5000 W over 1.7 m^2 -> ~294% efficiency

    with pytest.raises(SolarModuleValidationError, match="efficiency"):
        SolarModule(**values)


def test_catalog_rejects_duplicate_manufacturer_and_model() -> None:
    first = SolarModule(**MODULE)
    second = SolarModule(**MODULE)

    with pytest.raises(SolarModuleValidationError, match="duplicate"):
        SolarModuleCatalog((first, second))


@pytest.mark.parametrize("suffix", [".yaml", ".json"])
def test_loads_synthetic_catalog_from_yaml_or_json(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"modules{suffix}"
    document = {"modules": [MODULE]}
    if suffix == ".yaml":
        path.write_text(yaml.safe_dump(document), encoding="utf-8")
    else:
        path.write_text(json.dumps(document), encoding="utf-8")

    catalog = load_solar_module_catalog(path)

    assert len(catalog.modules) == 1
    assert catalog.modules[0].rated_power_w == 400.0
    assert catalog.modules[0].data_source == "synthetic-test-dataset"


def test_loader_reports_invalid_field_and_unsupported_format(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.yaml"
    invalid_entry = dict(MODULE, manufacturer="")
    invalid_path.write_text(yaml.safe_dump({"modules": [invalid_entry]}), encoding="utf-8")

    with pytest.raises(SolarModuleCatalogError, match="manufacturer"):
        load_solar_module_catalog(invalid_path)

    unsupported_path = tmp_path / "modules.txt"
    unsupported_path.write_text("modules: []", encoding="utf-8")
    with pytest.raises(SolarModuleCatalogError, match="suffix"):
        load_solar_module_catalog(unsupported_path)
