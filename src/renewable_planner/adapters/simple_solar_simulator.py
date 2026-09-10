"""Baseline PV-array simulator with a lossless inverter.

This is the CLI's default ``SolarArraySimulator`` when the optional pvlib
adapter has not been requested. It has no third-party dependency: DC power
per module comes from the dependency-free ``SolarProductionModel``, scaled
by module count, and the inverter is assumed lossless — so the inverter
loss is reported as exactly zero rather than estimated.
"""

from renewable_planner.domain.energy_profile import EnergyProfile, EnergySample
from renewable_planner.domain.solar_production import SolarProductionModel
from renewable_planner.domain.solar_simulation import (
    SolarSimulationRequest,
    SolarSimulationResult,
)


class SimpleSolarArraySimulator:
    """Scale single-module production by module count with no inverter loss."""

    def simulate(self, request: SolarSimulationRequest) -> SolarSimulationResult:
        """Return an array-level profile assuming a lossless inverter."""
        single_module_profile = SolarProductionModel().generate(
            request.module,
            request.timestamps,
            request.poa_irradiance_w_per_m2,
            request.ambient_temperature_c,
            technical_availability=request.technical_availability,
            loss_factor=request.loss_factor,
            source="SimpleSolarArraySimulator: single module",
        )
        dc_profile = EnergyProfile(
            samples=tuple(
                EnergySample(sample.timestamp, sample.power_mw * request.module_count)
                for sample in single_module_profile.samples
            ),
            source=f"SimpleSolarArraySimulator: {request.module_count} modules, DC",
        )
        return SolarSimulationResult(
            dc_profile=dc_profile,
            ac_profile=dc_profile,
            inverter_loss_mwh=0.0,
            inverter_loss_fraction=0.0,
        )
