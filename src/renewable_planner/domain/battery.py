"""Domain models for a basic battery energy-storage catalogue.

Mirrors ``domain.wind_turbine``/``domain.solar_module`` for the independent
``storage`` module: a manufacturer specification with no dispatch or
optimization behavior. That belongs to ``domain.battery_dispatch``.
"""

import math
from dataclasses import dataclass

from renewable_planner.domain.common import require_non_empty


class BatteryValidationError(ValueError):
    """Raised when a battery catalogue entry is physically invalid."""


def _require_finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BatteryValidationError(f"{field_name} must be a number")
    if not math.isfinite(value):
        raise BatteryValidationError(f"{field_name} must be finite")


def _require_finite_positive(value: float, field_name: str) -> None:
    _require_finite(value, field_name)
    if value <= 0:
        raise BatteryValidationError(f"{field_name} must be greater than zero")


@dataclass(frozen=True, slots=True)
class Battery:
    """Manufacturer specification used by preliminary storage analysis."""

    manufacturer: str
    model_name: str
    capacity_mwh: float
    max_charge_power_mw: float
    max_discharge_power_mw: float
    round_trip_efficiency_percent: float
    min_state_of_charge_fraction: float
    max_state_of_charge_fraction: float
    data_source: str
    data_version: str

    def __post_init__(self) -> None:
        for text, field_name in (
            (self.manufacturer, "manufacturer"),
            (self.model_name, "model_name"),
            (self.data_source, "data_source"),
            (self.data_version, "data_version"),
        ):
            try:
                require_non_empty(text, field_name)
            except ValueError as error:
                raise BatteryValidationError(f"{field_name} must be non-empty text") from error

        _require_finite_positive(self.capacity_mwh, "capacity_mwh")
        _require_finite_positive(self.max_charge_power_mw, "max_charge_power_mw")
        _require_finite_positive(self.max_discharge_power_mw, "max_discharge_power_mw")

        _require_finite(self.round_trip_efficiency_percent, "round_trip_efficiency_percent")
        if not 0 < self.round_trip_efficiency_percent <= 100:
            raise BatteryValidationError("round_trip_efficiency_percent must be within (0, 100]")

        _require_finite(self.min_state_of_charge_fraction, "min_state_of_charge_fraction")
        _require_finite(self.max_state_of_charge_fraction, "max_state_of_charge_fraction")
        if not (0 <= self.min_state_of_charge_fraction < self.max_state_of_charge_fraction <= 1):
            raise BatteryValidationError(
                "state-of-charge fractions must satisfy "
                "0 <= min_state_of_charge_fraction < max_state_of_charge_fraction <= 1"
            )


@dataclass(frozen=True, slots=True)
class BatteryCatalog:
    """Immutable collection of uniquely identified battery models."""

    batteries: tuple[Battery, ...]

    def __post_init__(self) -> None:
        identifiers = [(b.manufacturer.casefold(), b.model_name.casefold()) for b in self.batteries]
        if len(set(identifiers)) != len(identifiers):
            raise BatteryValidationError("catalog contains duplicate manufacturer/model entries")

    def find(self, manufacturer: str, model_name: str) -> Battery | None:
        """Find a battery by case-insensitive manufacturer and model."""
        identifier = (manufacturer.strip().casefold(), model_name.strip().casefold())
        return next(
            (
                battery
                for battery in self.batteries
                if (battery.manufacturer.casefold(), battery.model_name.casefold()) == identifier
            ),
            None,
        )
