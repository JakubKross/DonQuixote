"""Library-neutral input and output models for wind-farm simulation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from renewable_planner.domain.energy_profile import EnergyProfile
from renewable_planner.domain.wind_layout import TurbinePosition
from renewable_planner.domain.wind_turbine import WindTurbine


class WindSimulationValidationError(ValueError):
    """Raised when a wind simulation request or result is invalid."""


@dataclass(frozen=True, slots=True)
class WindSimulationRequest:
    """Time-series inputs for one wind turbine type and a farm layout."""

    turbine: WindTurbine
    positions: tuple[TurbinePosition, ...]
    timestamps: tuple[datetime, ...]
    wind_speeds_mps: tuple[float, ...]
    wind_directions_deg: tuple[float, ...]
    technical_availability: float = 1.0
    loss_factor: float = 0.0

    def __post_init__(self) -> None:
        if not self.positions:
            raise WindSimulationValidationError("positions must not be empty")
        if not self.timestamps:
            raise WindSimulationValidationError("timestamps must not be empty")
        if len(self.timestamps) != len(self.wind_speeds_mps) or len(self.timestamps) != len(
            self.wind_directions_deg
        ):
            raise WindSimulationValidationError(
                "timestamps, wind speeds and wind directions must have the same length"
            )
        for index, speed in enumerate(self.wind_speeds_mps):
            if (
                isinstance(speed, bool)
                or not isinstance(speed, (int, float))
                or not math.isfinite(speed)
                or speed < 0
            ):
                raise WindSimulationValidationError(f"wind speed at index {index} is invalid")
        for index, direction in enumerate(self.wind_directions_deg):
            if (
                isinstance(direction, bool)
                or not isinstance(direction, (int, float))
                or not math.isfinite(direction)
            ):
                raise WindSimulationValidationError(f"wind direction at index {index} is invalid")
        _fraction(self.technical_availability, "technical_availability")
        _fraction(self.loss_factor, "loss_factor")


@dataclass(frozen=True, slots=True)
class WindSimulationResult:
    """Standardized result of a wind-farm simulation."""

    no_wake_profile: EnergyProfile
    wake_profile: EnergyProfile
    wake_loss_mwh: float
    wake_loss_fraction: float
    turbine_profiles: tuple[EnergyProfile, ...]


def _fraction(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise WindSimulationValidationError(f"{name} must be finite and between 0 and 1")
    if not 0 <= value <= 1:
        raise WindSimulationValidationError(f"{name} must be finite and between 0 and 1")
    return float(value)
