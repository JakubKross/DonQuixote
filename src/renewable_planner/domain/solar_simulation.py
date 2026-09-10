"""Library-neutral input and output models for PV-array simulation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from renewable_planner.domain.energy_profile import EnergyProfile
from renewable_planner.domain.solar_module import SolarModule


class SolarSimulationValidationError(ValueError):
    """Raised when a solar simulation request or result is invalid."""


@dataclass(frozen=True, slots=True)
class SolarSimulationRequest:
    """Time-series inputs for one PV-module type tiled into an array."""

    module: SolarModule
    module_count: int
    timestamps: tuple[datetime, ...]
    poa_irradiance_w_per_m2: tuple[float, ...]
    ambient_temperature_c: tuple[float, ...]
    technical_availability: float = 1.0
    loss_factor: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.module_count, bool) or not isinstance(self.module_count, int):
            raise SolarSimulationValidationError("module_count must be an integer")
        if self.module_count <= 0:
            raise SolarSimulationValidationError("module_count must be greater than zero")
        if not self.timestamps:
            raise SolarSimulationValidationError("timestamps must not be empty")
        if len(self.timestamps) != len(self.poa_irradiance_w_per_m2) or len(self.timestamps) != len(
            self.ambient_temperature_c
        ):
            raise SolarSimulationValidationError(
                "timestamps, irradiance and temperature must have the same length"
            )
        for index, irradiance in enumerate(self.poa_irradiance_w_per_m2):
            if (
                isinstance(irradiance, bool)
                or not isinstance(irradiance, (int, float))
                or not math.isfinite(irradiance)
                or irradiance < 0
            ):
                raise SolarSimulationValidationError(f"irradiance at index {index} is invalid")
        for index, temperature in enumerate(self.ambient_temperature_c):
            if (
                isinstance(temperature, bool)
                or not isinstance(temperature, (int, float))
                or not math.isfinite(temperature)
            ):
                raise SolarSimulationValidationError(f"temperature at index {index} is invalid")
        _fraction(self.technical_availability, "technical_availability")
        _fraction(self.loss_factor, "loss_factor")


@dataclass(frozen=True, slots=True)
class SolarSimulationResult:
    """Standardized result of a PV-array simulation.

    ``dc_profile``/``ac_profile`` mirror the wind module's no-wake/with-wake
    pair with the physically meaningful PV analog: DC array output before
    the inverter and AC output after it.
    """

    dc_profile: EnergyProfile
    ac_profile: EnergyProfile
    inverter_loss_mwh: float
    inverter_loss_fraction: float


def _fraction(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SolarSimulationValidationError(f"{name} must be finite and between 0 and 1")
    if not 0 <= value <= 1:
        raise SolarSimulationValidationError(f"{name} must be finite and between 0 and 1")
    return float(value)
