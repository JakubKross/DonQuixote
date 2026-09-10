import pytest

from renewable_planner.domain import Battery, BatteryCatalog, BatteryValidationError

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


def test_domain_model_accepts_valid_battery_and_catalog_lookup() -> None:
    battery = Battery(**BATTERY)
    catalog = BatteryCatalog((battery,))

    assert catalog.find("fikcyjny storage", "fb-100") is battery


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("capacity_mwh", 0, "greater than zero"),
        ("max_charge_power_mw", -1, "greater than zero"),
        ("max_discharge_power_mw", float("inf"), "finite"),
        ("round_trip_efficiency_percent", 0, "round_trip_efficiency_percent"),
        ("round_trip_efficiency_percent", 101, "round_trip_efficiency_percent"),
    ],
)
def test_domain_model_rejects_invalid_units_or_values(
    field: str, value: float, message: str
) -> None:
    values = dict(BATTERY)
    values[field] = value

    with pytest.raises(BatteryValidationError, match=message):
        Battery(**values)


@pytest.mark.parametrize(
    ("min_fraction", "max_fraction"),
    [(0.5, 0.5), (0.9, 0.1), (-0.1, 0.9), (0.1, 1.1)],
)
def test_domain_model_rejects_invalid_state_of_charge_bounds(
    min_fraction: float, max_fraction: float
) -> None:
    values = dict(
        BATTERY,
        min_state_of_charge_fraction=min_fraction,
        max_state_of_charge_fraction=max_fraction,
    )

    with pytest.raises(BatteryValidationError, match="state-of-charge"):
        Battery(**values)


def test_catalog_rejects_duplicate_manufacturer_and_model() -> None:
    first = Battery(**BATTERY)
    second = Battery(**BATTERY)

    with pytest.raises(BatteryValidationError, match="duplicate"):
        BatteryCatalog((first, second))
