"""Simplified hourly energy production model for one PV module or string."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from renewable_planner.domain.common import require_aware
from renewable_planner.domain.energy_profile import EnergyProfile, EnergySample
from renewable_planner.domain.solar_module import (
    STANDARD_TEST_CONDITIONS_IRRADIANCE_W_PER_M2,
    SolarModule,
)

STANDARD_TEST_CONDITIONS_TEMPERATURE_C = 25.0


class SolarProductionValidationError(ValueError):
    """Raised when solar-production inputs are invalid."""


def _require_fraction(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SolarProductionValidationError(f"{name} must be a number")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise SolarProductionValidationError(f"{name} must be finite and between 0 and 1")
    return float(value)


def _require_irradiance(value: float, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SolarProductionValidationError(f"irradiance at index {index} must be a number")
    if not math.isfinite(value) or value < 0:
        raise SolarProductionValidationError(
            f"irradiance at index {index} must be finite and non-negative"
        )
    return float(value)


def _require_temperature(value: float, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SolarProductionValidationError(
            f"ambient temperature at index {index} must be a finite number"
        )
    return float(value)


def _availability_values(
    availability: float | Sequence[float], expected_length: int
) -> tuple[float, ...]:
    if isinstance(availability, (int, float)) and not isinstance(availability, bool):
        value = _require_fraction(availability, "technical_availability")
        return (value,) * expected_length
    if isinstance(availability, bool) or not isinstance(availability, Sequence):
        raise SolarProductionValidationError(
            "technical_availability must be a number or a sequence of numbers"
        )
    if len(availability) != expected_length:
        raise SolarProductionValidationError(
            "technical_availability and poa_irradiance_w_per_m2 must have the same length"
        )
    return tuple(
        _require_fraction(value, f"technical_availability at index {index}")
        for index, value in enumerate(availability)
    )


class SolarProductionModel:
    """Calculate a one-module/string hourly profile without pvlib.

    Uses a linear irradiance model with a temperature-coefficient derating,
    assuming the module's cell temperature equals ambient temperature. Real
    modules run hotter than ambient under irradiance (self-heating), so this
    is a deliberate first-version simplification; the optional pvlib adapter
    models this more accurately.
    """

    def generate(
        self,
        module: SolarModule,
        timestamps: Sequence[datetime],
        poa_irradiance_w_per_m2: Sequence[float],
        ambient_temperature_c: Sequence[float],
        *,
        technical_availability: float | Sequence[float] = 1.0,
        loss_factor: float = 0.0,
        source: str = "simplified solar production model",
    ) -> EnergyProfile:
        if not (len(timestamps) == len(poa_irradiance_w_per_m2) == len(ambient_temperature_c)):
            raise SolarProductionValidationError(
                "timestamps, poa_irradiance_w_per_m2 and ambient_temperature_c must have "
                "the same length"
            )
        if not timestamps:
            raise SolarProductionValidationError("hourly input series must not be empty")
        availability = _availability_values(technical_availability, len(timestamps))
        losses = _require_fraction(loss_factor, "loss_factor")

        samples: list[EnergySample] = []
        for index, (timestamp, irradiance, temperature, available) in enumerate(
            zip(
                timestamps,
                poa_irradiance_w_per_m2,
                ambient_temperature_c,
                availability,
                strict=True,
            )
        ):
            try:
                require_aware(timestamp, f"timestamps[{index}]")
            except ValueError as error:
                raise SolarProductionValidationError(str(error)) from error
            irradiance_value = _require_irradiance(irradiance, index)
            temperature_value = _require_temperature(temperature, index)
            power_w = _module_power_w(module, irradiance_value, temperature_value)
            power_mw = power_w * available * (1 - losses) / 1_000_000
            samples.append(EnergySample(timestamp=timestamp, power_mw=power_mw))
        try:
            return EnergyProfile(samples=tuple(samples), source=source)
        except ValueError as error:
            raise SolarProductionValidationError(str(error)) from error


def _module_power_w(
    module: SolarModule, irradiance_w_per_m2: float, ambient_temperature_c: float
) -> float:
    """Return DC power for one module using a linear irradiance model."""
    temperature_delta = ambient_temperature_c - STANDARD_TEST_CONDITIONS_TEMPERATURE_C
    derate = 1 + (module.temperature_coefficient_pct_per_c / 100) * temperature_delta
    power_w = (
        module.rated_power_w
        * (irradiance_w_per_m2 / STANDARD_TEST_CONDITIONS_IRRADIANCE_W_PER_M2)
        * derate
    )
    return max(power_w, 0.0)
