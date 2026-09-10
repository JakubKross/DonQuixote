from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.adapters.simple_solar_simulator import SimpleSolarArraySimulator
from renewable_planner.domain import SolarModule, SolarSimulationRequest

MODULE = SolarModule(
    manufacturer="Test Solar",
    model_name="TS-400",
    rated_power_w=400,
    width_m=1.0,
    height_m=1.7,
    temperature_coefficient_pct_per_c=-0.4,
    data_source="test",
    data_version="v1",
)
START = datetime(2026, 6, 1, 8, tzinfo=UTC)


def _request(module_count: int) -> SolarSimulationRequest:
    return SolarSimulationRequest(
        module=MODULE,
        module_count=module_count,
        timestamps=tuple(START + timedelta(hours=index) for index in range(3)),
        poa_irradiance_w_per_m2=(200.0, 600.0, 900.0),
        ambient_temperature_c=(15.0, 25.0, 30.0),
    )


def test_reports_no_inverter_loss() -> None:
    result = SimpleSolarArraySimulator().simulate(_request(10))

    assert result.inverter_loss_mwh == 0.0
    assert result.inverter_loss_fraction == 0.0
    assert result.dc_profile == result.ac_profile


def test_scales_linearly_with_module_count() -> None:
    single = SimpleSolarArraySimulator().simulate(_request(1))
    tenfold = SimpleSolarArraySimulator().simulate(_request(10))

    assert tenfold.dc_profile.total_energy_mwh == pytest.approx(
        single.dc_profile.total_energy_mwh * 10
    )


def test_is_deterministic_for_the_same_request() -> None:
    request = _request(5)
    simulator = SimpleSolarArraySimulator()

    first = simulator.simulate(request)
    second = simulator.simulate(request)

    assert first.dc_profile.samples == second.dc_profile.samples
