"""Optional PyWake adapter for wind-farm wake simulation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from renewable_planner.domain.energy_profile import EnergyProfile, EnergySample, sum_profiles
from renewable_planner.domain.wind_production import WindProductionModel
from renewable_planner.domain.wind_simulation import (
    WindSimulationRequest,
    WindSimulationResult,
)


class PyWakeUnavailableError(RuntimeError):
    """Raised when the optional PyWake dependency is not installed."""


class PyWakeWindFarmSimulator:
    """Adapt PyWake's time-series result to the project's wind port.

    The adapter uses a uniform site and NOJ wake model. Domain models do not
    import PyWake. A constant CT curve is used because the current domain
    turbine catalogue does not yet contain CT data.
    """

    def __init__(self, model_factory: Callable[[Any, Any], Any] | None = None) -> None:
        self._model_factory = model_factory

    def simulate(self, request: WindSimulationRequest) -> WindSimulationResult:
        try:
            import numpy as np
            from py_wake import NOJ
            from py_wake.site import UniformSite
            from py_wake.wind_turbines import WindTurbines
            from py_wake.wind_turbines.power_ct_functions import PowerCtTabular
        except ImportError as error:
            raise PyWakeUnavailableError(
                "PyWake adapter requires the optional 'py-wake' dependency"
            ) from error

        curve = request.turbine.power_curve
        power_ct = PowerCtTabular(
            ws=[point.wind_speed_mps for point in curve],
            power=[point.power_kw * 1000 for point in curve],
            power_unit="w",
            ct=[0.8] * len(curve),
        )
        wind_turbines = WindTurbines(
            names=[request.turbine.model_name],
            diameters=[request.turbine.rotor_diameter_m],
            hub_heights=[request.turbine.hub_height_m],
            powerCtFunctions=[power_ct],
        )
        # p_ws was removed from UniformSite in py-wake >= 2.6; per-timestep wind
        # speeds are supplied directly to the model call below via `ws=ws`, so
        # the site itself only needs a wind-direction probability and turbulence
        # intensity.
        site = UniformSite(p_wd=[1], ti=0.1)
        model = (
            self._model_factory(site, wind_turbines)
            if self._model_factory
            else NOJ(site, wind_turbines)
        )
        x = np.asarray([position.x_m for position in request.positions], dtype=float)
        y = np.asarray([position.y_m for position in request.positions], dtype=float)
        ws = np.asarray(request.wind_speeds_mps, dtype=float)
        wd = np.asarray(request.wind_directions_deg, dtype=float)
        time = np.arange(len(request.timestamps), dtype=float)
        simulation = model(x, y, wd=wd, ws=ws, time=time)
        wake_power_w = _power_array(simulation, len(request.timestamps), len(request.positions))

        base_model = WindProductionModel()
        no_wake_single = base_model.generate(
            request.turbine,
            request.timestamps,
            request.wind_speeds_mps,
            technical_availability=request.technical_availability,
            loss_factor=request.loss_factor,
            source="PyWake adapter: no-wake reference",
        )
        no_wake_profiles = tuple(
            EnergyProfile(
                samples=no_wake_single.samples,
                source=f"PyWake adapter: no-wake turbine {index}",
            )
            for index in range(len(request.positions))
        )
        turbine_profiles = tuple(
            _profile_from_power(
                request,
                wake_power_w[:, index],
                f"PyWake adapter: turbine {index} with wake",
            )
            for index in range(len(request.positions))
        )
        no_wake_profile = sum_profiles(no_wake_profiles, "PyWake adapter: aggregate without wake")
        wake_profile = sum_profiles(turbine_profiles, "PyWake adapter: aggregate with wake")
        no_wake_energy = no_wake_profile.total_energy_mwh
        wake_loss = max(0.0, no_wake_energy - wake_profile.total_energy_mwh)
        return WindSimulationResult(
            no_wake_profile=no_wake_profile,
            wake_profile=wake_profile,
            wake_loss_mwh=wake_loss,
            wake_loss_fraction=wake_loss / no_wake_energy if no_wake_energy else 0.0,
            turbine_profiles=turbine_profiles,
        )


def _power_array(simulation: Any, time_count: int, turbine_count: int) -> Any:
    import numpy as np

    power = simulation["power"] if "power" in simulation else simulation["Power"]
    if hasattr(power, "dims") and "time" in power.dims and "wt" in power.dims:
        power = power.transpose("time", "wt")
    values = np.asarray(getattr(power, "values", power), dtype=float)
    values = np.squeeze(values)
    if values.shape != (time_count, turbine_count):
        raise RuntimeError(
            f"unexpected PyWake power shape {values.shape}; expected {(time_count, turbine_count)}"
        )
    return values


def _profile_from_power(request: WindSimulationRequest, power_w: Any, source: str) -> EnergyProfile:
    availability = request.technical_availability * (1 - request.loss_factor)
    samples = tuple(
        EnergySample(timestamp, float(power) * availability / 1_000_000)
        for timestamp, power in zip(request.timestamps, power_w, strict=True)
    )
    return EnergyProfile(samples=samples, source=source)
