"""Optional pvlib adapter for PV-array inverter modeling."""

from __future__ import annotations

from renewable_planner.domain.energy_profile import EnergyProfile, EnergySample
from renewable_planner.domain.solar_production import SolarProductionModel
from renewable_planner.domain.solar_simulation import (
    SolarSimulationRequest,
    SolarSimulationResult,
)


class PvlibUnavailableError(RuntimeError):
    """Raised when the optional pvlib dependency is not installed."""


class PvlibSolarArraySimulator:
    """Adapt pvlib's PVWatts inverter model to the project's solar port.

    DC power per module comes from the dependency-free
    ``SolarProductionModel`` — the domain does not import pvlib. This
    adapter's only added value over ``SimpleSolarArraySimulator`` is a more
    realistic AC conversion via pvlib's PVWatts inverter efficiency curve
    instead of assuming a lossless inverter.
    """

    def __init__(self, inverter_dc_rating_w: float | None = None) -> None:
        self._inverter_dc_rating_w = inverter_dc_rating_w

    def simulate(self, request: SolarSimulationRequest) -> SolarSimulationResult:
        """Return the DC array profile and the PVWatts-converted AC profile."""
        try:
            import numpy as np
            from pvlib.inverter import pvwatts
        except ImportError as error:
            raise PvlibUnavailableError(
                "pvlib adapter requires the optional 'pvlib' dependency"
            ) from error

        single_module_profile = SolarProductionModel().generate(
            request.module,
            request.timestamps,
            request.poa_irradiance_w_per_m2,
            request.ambient_temperature_c,
            technical_availability=request.technical_availability,
            loss_factor=request.loss_factor,
            source="pvlib adapter: single-module DC reference",
        )
        dc_power_w = np.asarray(
            [
                sample.power_mw * request.module_count * 1_000_000
                for sample in single_module_profile.samples
            ],
            dtype=float,
        )
        pdc0 = self._inverter_dc_rating_w or request.module.rated_power_w * request.module_count
        ac_power_w = np.clip(pvwatts(dc_power_w, pdc0), 0, None)

        dc_profile = EnergyProfile(
            samples=tuple(
                EnergySample(sample.timestamp, sample.power_mw * request.module_count)
                for sample in single_module_profile.samples
            ),
            source=f"pvlib adapter: {request.module_count} modules, DC",
        )
        ac_profile = EnergyProfile(
            samples=tuple(
                EnergySample(timestamp, float(power) / 1_000_000)
                for timestamp, power in zip(request.timestamps, ac_power_w, strict=True)
            ),
            source="pvlib adapter: AC array total (PVWatts inverter)",
        )
        dc_energy = dc_profile.total_energy_mwh
        ac_energy = ac_profile.total_energy_mwh
        loss = max(0.0, dc_energy - ac_energy)
        return SolarSimulationResult(
            dc_profile=dc_profile,
            ac_profile=ac_profile,
            inverter_loss_mwh=loss,
            inverter_loss_fraction=loss / dc_energy if dc_energy else 0.0,
        )
