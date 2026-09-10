from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.adapters.pvlib_solar import PvlibSolarArraySimulator
from renewable_planner.domain import SolarModule, SolarSimulationRequest

pytestmark = pytest.mark.pvlib
pytest.importorskip("pvlib")


MODULE = SolarModule(
    manufacturer="Integration Solar",
    model_name="IS-400",
    rated_power_w=400,
    width_m=1.0,
    height_m=1.7,
    temperature_coefficient_pct_per_c=-0.4,
    data_source="integration-test",
    data_version="v1",
)
START = datetime(2026, 6, 1, 8, tzinfo=UTC)


def test_pvlib_adapter_returns_deterministic_ac_profile() -> None:
    request = SolarSimulationRequest(
        module=MODULE,
        module_count=20,
        timestamps=tuple(START + timedelta(hours=index) for index in range(4)),
        poa_irradiance_w_per_m2=(0.0, 300.0, 700.0, 1000.0),
        ambient_temperature_c=(15.0, 20.0, 28.0, 32.0),
    )
    simulator = PvlibSolarArraySimulator()

    first = simulator.simulate(request)
    second = simulator.simulate(request)

    assert first.ac_profile == second.ac_profile
    assert first.dc_profile.total_energy_mwh >= first.ac_profile.total_energy_mwh
    assert first.inverter_loss_mwh == pytest.approx(
        first.dc_profile.total_energy_mwh - first.ac_profile.total_energy_mwh
    )
    assert first.ac_profile.samples[0].power_mw == 0.0


def test_pvlib_adapter_respects_the_inverter_dc_rating() -> None:
    request = SolarSimulationRequest(
        module=MODULE,
        module_count=20,
        timestamps=(START,),
        poa_irradiance_w_per_m2=(1000.0,),
        ambient_temperature_c=(25.0,),
    )
    undersized_inverter = PvlibSolarArraySimulator(inverter_dc_rating_w=4000.0)

    result = undersized_inverter.simulate(request)

    # 20 modules * 400 W = 8000 W DC into a 4000 W-rated inverter must clip.
    assert result.ac_profile.samples[0].power_mw < result.dc_profile.samples[0].power_mw
