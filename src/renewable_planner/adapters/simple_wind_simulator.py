"""Baseline wind-farm simulator with no wake modeling.

This is the CLI's default ``WindFarmSimulator`` when the optional PyWake
adapter has not been requested. It has no third-party dependency: wind is
assumed uniform across the site, so every turbine gets the same single-
turbine production profile, and the wake loss is reported as exactly zero
rather than estimated.
"""

from renewable_planner.domain.energy_profile import EnergyProfile, sum_profiles
from renewable_planner.domain.wind_production import WindProductionModel
from renewable_planner.domain.wind_simulation import (
    WindSimulationRequest,
    WindSimulationResult,
)


class SimpleWindFarmSimulator:
    """Aggregate identical single-turbine production across every position."""

    def simulate(self, request: WindSimulationRequest) -> WindSimulationResult:
        """Return a farm-level profile with no wake loss applied."""
        single_turbine_profile = WindProductionModel().generate(
            request.turbine,
            request.timestamps,
            request.wind_speeds_mps,
            technical_availability=request.technical_availability,
            loss_factor=request.loss_factor,
            source="SimpleWindFarmSimulator: single turbine, no wake modeled",
        )
        turbine_profiles = tuple(
            EnergyProfile(
                samples=single_turbine_profile.samples,
                source=f"SimpleWindFarmSimulator: turbine {index}, no wake modeled",
            )
            for index in range(len(request.positions))
        )
        aggregate = sum_profiles(
            turbine_profiles, "SimpleWindFarmSimulator: farm aggregate, no wake modeled"
        )
        return WindSimulationResult(
            no_wake_profile=aggregate,
            wake_profile=aggregate,
            wake_loss_mwh=0.0,
            wake_loss_fraction=0.0,
            turbine_profiles=turbine_profiles,
        )
