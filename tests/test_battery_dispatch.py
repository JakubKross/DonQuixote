from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.domain import (
    Battery,
    BatteryDispatcher,
    BatteryDispatchValidationError,
    EnergyProfile,
    EnergySample,
)

BATTERY = Battery(
    manufacturer="Test Storage",
    model_name="TB-10",
    capacity_mwh=10.0,
    max_charge_power_mw=5.0,
    max_discharge_power_mw=5.0,
    round_trip_efficiency_percent=90.0,
    min_state_of_charge_fraction=0.0,
    max_state_of_charge_fraction=1.0,
    data_source="test",
    data_version="v1",
)
START = datetime(2026, 1, 1, tzinfo=UTC)


def _profile(*powers: float) -> EnergyProfile:
    samples = tuple(
        EnergySample(START + timedelta(hours=index), power) for index, power in enumerate(powers)
    )
    return EnergyProfile(samples=samples, source="test")


def test_charges_with_surplus_above_the_target() -> None:
    profile = _profile(8.0)  # 3 MW surplus above target=5
    result = BatteryDispatcher().simulate(
        BATTERY, profile, target_power_mw=5.0, initial_state_of_charge_fraction=0.0
    )

    sample = result.samples[0]
    assert sample.charge_power_mw == pytest.approx(3.0)
    assert sample.delivered_power_mw == pytest.approx(5.0)
    assert sample.curtailed_power_mw == 0.0
    assert result.charged_energy_mwh == pytest.approx(3.0)
    # stored = 3.0 * 0.9 = 2.7 MWh -> SoC = 2.7/10 = 0.27
    assert sample.state_of_charge_fraction == pytest.approx(0.27)
    assert result.round_trip_loss_mwh == pytest.approx(0.3)


def test_discharges_to_fill_a_gap_below_the_target() -> None:
    profile = _profile(2.0)  # 3 MW deficit below target=5
    result = BatteryDispatcher().simulate(
        BATTERY, profile, target_power_mw=5.0, initial_state_of_charge_fraction=0.5
    )

    sample = result.samples[0]
    assert sample.discharge_power_mw == pytest.approx(3.0)
    assert sample.delivered_power_mw == pytest.approx(5.0)
    # SoC started at 5 MWh, discharged 3 MWh -> 2 MWh -> 0.2 fraction
    assert sample.state_of_charge_fraction == pytest.approx(0.2)
    assert result.discharged_energy_mwh == pytest.approx(3.0)


def test_curtails_surplus_beyond_charge_power_or_headroom() -> None:
    profile = _profile(20.0)  # far above target and above max charge power
    result = BatteryDispatcher().simulate(
        BATTERY, profile, target_power_mw=5.0, initial_state_of_charge_fraction=0.0
    )

    sample = result.samples[0]
    # surplus = 15, but max_charge_power_mw = 5
    assert sample.charge_power_mw == pytest.approx(5.0)
    assert sample.curtailed_power_mw == pytest.approx(10.0)
    assert result.curtailed_energy_mwh == pytest.approx(10.0)
    # Delivery must stay capped at the target even though the battery could
    # not absorb all of the surplus — the leftover is curtailed, never
    # exported above the connection limit.
    assert sample.delivered_power_mw == pytest.approx(5.0)


@pytest.mark.parametrize("production_mw", [0.0, 2.0, 5.0, 8.0, 20.0])
def test_hourly_power_balances_between_production_battery_and_grid(
    production_mw: float,
) -> None:
    """production + discharge == delivered + charge + curtailed, every hour."""
    profile = _profile(production_mw)
    result = BatteryDispatcher().simulate(
        BATTERY, profile, target_power_mw=5.0, initial_state_of_charge_fraction=0.3
    )

    sample = result.samples[0]
    assert production_mw + sample.discharge_power_mw == pytest.approx(
        sample.delivered_power_mw + sample.charge_power_mw + sample.curtailed_power_mw
    )
    assert sample.delivered_power_mw <= 5.0 + 1e-9


def test_stops_charging_once_battery_reaches_max_state_of_charge() -> None:
    profile = _profile(8.0)
    almost_full = replace(BATTERY, max_state_of_charge_fraction=0.5)
    result = BatteryDispatcher().simulate(
        almost_full, profile, target_power_mw=5.0, initial_state_of_charge_fraction=0.5
    )

    sample = result.samples[0]
    assert sample.charge_power_mw == 0.0
    assert sample.curtailed_power_mw == pytest.approx(3.0)
    assert sample.delivered_power_mw == pytest.approx(5.0)


def test_stops_discharging_once_battery_reaches_min_state_of_charge() -> None:
    profile = _profile(2.0)
    result = BatteryDispatcher().simulate(
        BATTERY, profile, target_power_mw=5.0, initial_state_of_charge_fraction=0.0
    )

    sample = result.samples[0]
    assert sample.discharge_power_mw == 0.0
    assert sample.delivered_power_mw == pytest.approx(2.0)


def test_rejects_initial_state_of_charge_outside_battery_bounds() -> None:
    profile = _profile(5.0)

    with pytest.raises(BatteryDispatchValidationError, match="allowed"):
        BatteryDispatcher().simulate(
            BATTERY, profile, target_power_mw=5.0, initial_state_of_charge_fraction=1.5
        )


def test_is_deterministic_for_the_same_inputs() -> None:
    profile = _profile(8.0, 2.0, 5.0)
    dispatcher = BatteryDispatcher()

    first = dispatcher.simulate(BATTERY, profile, 5.0, 0.2)
    second = dispatcher.simulate(BATTERY, profile, 5.0, 0.2)

    assert first == second
