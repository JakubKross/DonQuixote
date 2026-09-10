from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.adapters.pywake_wind import PyWakeWindFarmSimulator
from renewable_planner.domain import (
    PowerCurvePoint,
    TurbinePosition,
    WindSimulationRequest,
    WindTurbine,
)

pytestmark = pytest.mark.pywake
pytest.importorskip("py_wake")


TURBINE = WindTurbine(
    manufacturer="Integration Wind",
    model_name="IW-100",
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
    data_source="integration-test",
    data_version="v1",
)


def test_pywake_adapter_returns_deterministic_wake_profiles() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    request = WindSimulationRequest(
        turbine=TURBINE,
        positions=(TurbinePosition(0, 0), TurbinePosition(500, 0)),
        timestamps=tuple(start + timedelta(hours=index) for index in range(4)),
        wind_speeds_mps=(8, 8, 8, 8),
        wind_directions_deg=(270, 270, 270, 270),
    )
    simulator = PyWakeWindFarmSimulator()

    first = simulator.simulate(request)
    second = simulator.simulate(request)

    assert first.wake_profile == second.wake_profile
    assert first.no_wake_profile.total_energy_mwh >= first.wake_profile.total_energy_mwh
    assert first.wake_loss_mwh == pytest.approx(
        first.no_wake_profile.total_energy_mwh - first.wake_profile.total_energy_mwh
    )
    assert len(first.turbine_profiles) == 2
