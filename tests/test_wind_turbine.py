import json
from pathlib import Path

import pytest
import yaml

from renewable_planner.adapters.wind_catalog import (
    WindTurbineCatalogError,
    load_wind_turbine_catalog,
)
from renewable_planner.domain import (
    PowerCurvePoint,
    WindTurbine,
    WindTurbineCatalog,
    WindTurbineValidationError,
)

TURBINE = {
    "manufacturer": "Fikcyjny Wind",
    "model_name": "FW-500",
    "rated_power_kw": 500,
    "rotor_diameter_m": 82,
    "hub_height_m": 80,
    "cut_in_wind_speed_mps": 3,
    "rated_wind_speed_mps": 12,
    "cut_out_wind_speed_mps": 25,
    "power_curve": [
        {"wind_speed_mps": 3, "power_kw": 0},
        {"wind_speed_mps": 6, "power_kw": 100},
        {"wind_speed_mps": 12, "power_kw": 500},
        {"wind_speed_mps": 25, "power_kw": 0},
    ],
    "data_source": "synthetic-test-dataset",
    "data_version": "2026-01",
}


def test_domain_model_accepts_valid_turbine_and_catalog_lookup() -> None:
    turbine = WindTurbine(
        manufacturer="Fikcyjny Wind",
        model_name="FW-500",
        rated_power_kw=500,
        rotor_diameter_m=82,
        hub_height_m=80,
        cut_in_wind_speed_mps=3,
        rated_wind_speed_mps=12,
        cut_out_wind_speed_mps=25,
        power_curve=(
            PowerCurvePoint(3, 0),
            PowerCurvePoint(12, 500),
        ),
        data_source="synthetic-test-dataset",
        data_version="2026-01",
    )
    catalog = WindTurbineCatalog((turbine,))

    assert catalog.find("fikcyjny wind", "fw-500") is turbine


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("rated_power_kw", 0, "greater than zero"),
        ("rotor_diameter_m", -1, "non-negative"),
        ("cut_out_wind_speed_mps", float("inf"), "finite"),
    ],
)
def test_domain_model_rejects_invalid_units_or_values(
    field: str, value: float, message: str
) -> None:
    values = dict(TURBINE)
    values["power_curve"] = tuple(PowerCurvePoint(**point) for point in TURBINE["power_curve"])
    values[field] = value

    with pytest.raises(WindTurbineValidationError, match=message):
        WindTurbine(**values)


def test_domain_model_rejects_non_monotonic_curve() -> None:
    values = dict(TURBINE)
    values["power_curve"] = (
        PowerCurvePoint(3, 0),
        PowerCurvePoint(3, 50),
    )

    with pytest.raises(WindTurbineValidationError, match="strictly increasing"):
        WindTurbine(**values)


def test_catalog_rejects_duplicate_manufacturer_and_model() -> None:
    values = dict(TURBINE)
    values["power_curve"] = tuple(PowerCurvePoint(**point) for point in TURBINE["power_curve"])
    first = WindTurbine(**values)
    second = WindTurbine(**values)

    with pytest.raises(WindTurbineValidationError, match="duplicate"):
        WindTurbineCatalog((first, second))


@pytest.mark.parametrize("suffix", [".yaml", ".json"])
def test_loads_synthetic_catalog_from_yaml_or_json(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"turbines{suffix}"
    document = {"turbines": [TURBINE]}
    if suffix == ".yaml":
        path.write_text(yaml.safe_dump(document), encoding="utf-8")
    else:
        path.write_text(json.dumps(document), encoding="utf-8")

    catalog = load_wind_turbine_catalog(path)

    assert len(catalog.turbines) == 1
    assert catalog.turbines[0].rated_power_kw == 500.0
    assert catalog.turbines[0].data_source == "synthetic-test-dataset"


def test_loader_reports_invalid_field_and_unsupported_format(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.yaml"
    invalid_entry = dict(TURBINE, manufacturer="")
    invalid_path.write_text(yaml.safe_dump({"turbines": [invalid_entry]}), encoding="utf-8")

    with pytest.raises(WindTurbineCatalogError, match="manufacturer"):
        load_wind_turbine_catalog(invalid_path)

    unsupported_path = tmp_path / "turbines.txt"
    unsupported_path.write_text("turbines: []", encoding="utf-8")
    with pytest.raises(WindTurbineCatalogError, match="suffix"):
        load_wind_turbine_catalog(unsupported_path)
