from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.application.storage import DispatchBattery, DispatchBatteryCommand
from renewable_planner.domain import Battery, EnergyProfile, EnergySample

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


def test_execute_delegates_to_the_battery_dispatcher() -> None:
    use_case = DispatchBattery()

    result = use_case.execute(
        DispatchBatteryCommand(
            profile=_profile(8.0),
            battery=BATTERY,
            target_power_mw=5.0,
            initial_state_of_charge_fraction=0.0,
        )
    )

    assert result.samples[0].charge_power_mw == pytest.approx(3.0)


def test_is_deterministic_for_the_same_inputs() -> None:
    use_case = DispatchBattery()
    command = DispatchBatteryCommand(
        profile=_profile(8.0, 2.0),
        battery=BATTERY,
        target_power_mw=5.0,
        initial_state_of_charge_fraction=0.2,
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first == second
