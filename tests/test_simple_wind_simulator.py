from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.adapters.simple_wind_simulator import SimpleWindFarmSimulator
from renewable_planner.domain import (
    PowerCurvePoint,
    TurbinePosition,
    WindSimulationRequest,
    WindTurbine,
)

TURBINE = WindTurbine(
    manufacturer="Test Wind",
    model_name="TW-100",
    rated_power_kw=100,
    rotor_diameter_m=100,
    hub_height_m=100,
    cut_in_wind_speed_mps=3,
    rated_wind_speed_mps=10,
    cut_out_wind_speed_mps=25,
    power_curve=(
        PowerCurvePoint(3, 0),
        PowerCurvePoint(10, 100),
        PowerCurvePoint(25, 0),
    ),
    data_source="test",
    data_version="v1",
)
START = datetime(2026, 1, 1, tzinfo=UTC)


def _request(position_count: int) -> WindSimulationRequest:
    return WindSimulationRequest(
        turbine=TURBINE,
        positions=tuple(TurbinePosition(index * 500, 0) for index in range(position_count)),
        timestamps=tuple(START + timedelta(hours=index) for index in range(3)),
        wind_speeds_mps=(8, 10, 12),
        wind_directions_deg=(270, 270, 270),
    )


def test_reports_no_wake_loss() -> None:
    result = SimpleWindFarmSimulator().simulate(_request(3))

    assert result.wake_loss_mwh == 0.0
    assert result.wake_loss_fraction == 0.0
    assert result.no_wake_profile == result.wake_profile


def test_aggregate_is_the_sum_of_identical_turbine_profiles() -> None:
    result = SimpleWindFarmSimulator().simulate(_request(3))

    assert len(result.turbine_profiles) == 3
    assert result.no_wake_profile.total_energy_mwh == pytest.approx(
        sum(profile.total_energy_mwh for profile in result.turbine_profiles)
    )
    single_turbine_energy = result.turbine_profiles[0].total_energy_mwh
    assert all(
        profile.total_energy_mwh == single_turbine_energy for profile in result.turbine_profiles
    )


def test_is_deterministic_for_the_same_request() -> None:
    request = _request(2)
    simulator = SimpleWindFarmSimulator()

    first = simulator.simulate(request)
    second = simulator.simulate(request)

    assert first.wake_profile.samples == second.wake_profile.samples
