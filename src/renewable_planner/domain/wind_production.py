"""Simplified hourly energy production model for one wind turbine."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from renewable_planner.domain.common import require_aware
from renewable_planner.domain.energy_profile import EnergyProfile, EnergySample
from renewable_planner.domain.wind_turbine import WindTurbine


class WindProductionValidationError(ValueError):
    """Raised when wind-production inputs are invalid."""


def _require_fraction(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WindProductionValidationError(f"{name} must be a number")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise WindProductionValidationError(f"{name} must be finite and between 0 and 1")
    return float(value)


def _require_wind_speed(value: float, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WindProductionValidationError(f"wind speed at index {index} must be a number")
    if not math.isfinite(value) or value < 0:
        raise WindProductionValidationError(
            f"wind speed at index {index} must be finite and non-negative"
        )
    return float(value)


def _availability_values(
    availability: float | Sequence[float], expected_length: int
) -> tuple[float, ...]:
    if isinstance(availability, (int, float)) and not isinstance(availability, bool):
        value = _require_fraction(availability, "technical_availability")
        return (value,) * expected_length
    if isinstance(availability, bool) or not isinstance(availability, Sequence):
        raise WindProductionValidationError(
            "technical_availability must be a number or a sequence of numbers"
        )
    if len(availability) != expected_length:
        raise WindProductionValidationError(
            "technical_availability and wind_speeds_mps must have the same length"
        )
    return tuple(
        _require_fraction(value, f"technical_availability at index {index}")
        for index, value in enumerate(availability)
    )


class WindProductionModel:
    """Calculate a one-turbine hourly profile without wake modelling."""

    def generate(
        self,
        turbine: WindTurbine,
        timestamps: Sequence[datetime],
        wind_speeds_mps: Sequence[float],
        *,
        technical_availability: float | Sequence[float] = 1.0,
        loss_factor: float = 0.0,
        source: str = "simplified wind production model",
    ) -> EnergyProfile:
        if len(timestamps) != len(wind_speeds_mps):
            raise WindProductionValidationError(
                "timestamps and wind_speeds_mps must have the same length"
            )
        if not timestamps:
            raise WindProductionValidationError("hourly input series must not be empty")
        availability = _availability_values(technical_availability, len(timestamps))
        losses = _require_fraction(loss_factor, "loss_factor")

        samples: list[EnergySample] = []
        for index, (timestamp, wind_speed, available) in enumerate(
            zip(timestamps, wind_speeds_mps, availability, strict=True)
        ):
            try:
                require_aware(timestamp, f"timestamps[{index}]")
            except ValueError as error:
                raise WindProductionValidationError(str(error)) from error
            speed = _require_wind_speed(wind_speed, index)
            power_mw = _interpolate_power_kw(turbine, speed) * available * (1 - losses) / 1000
            samples.append(EnergySample(timestamp=timestamp, power_mw=power_mw))
        try:
            return EnergyProfile(samples=tuple(samples), source=source)
        except ValueError as error:
            raise WindProductionValidationError(str(error)) from error


def _interpolate_power_kw(turbine: WindTurbine, wind_speed_mps: float) -> float:
    """Interpolate linearly inside the curve and return zero outside it."""
    if (
        wind_speed_mps < turbine.cut_in_wind_speed_mps
        or wind_speed_mps >= turbine.cut_out_wind_speed_mps
    ):
        return 0.0

    curve = turbine.power_curve
    if wind_speed_mps < curve[0].wind_speed_mps or wind_speed_mps > curve[-1].wind_speed_mps:
        return 0.0
    for left, right in zip(curve, curve[1:], strict=False):
        if left.wind_speed_mps <= wind_speed_mps <= right.wind_speed_mps:
            ratio = (wind_speed_mps - left.wind_speed_mps) / (
                right.wind_speed_mps - left.wind_speed_mps
            )
            return left.power_kw + ratio * (right.power_kw - left.power_kw)
    return curve[-1].power_kw
