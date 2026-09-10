"""Domain models for a basic PV-module catalogue.

Mirrors ``domain.wind_turbine`` for the independent ``solar`` module: a
manufacturer specification with no simulation-library behavior. Only
independently measurable quantities are stored (rated power, physical
dimensions, temperature coefficient); STC efficiency is derived from them
rather than stored as a separate, potentially inconsistent field.
"""

import math
from dataclasses import dataclass

from renewable_planner.domain.common import require_non_empty

STANDARD_TEST_CONDITIONS_IRRADIANCE_W_PER_M2 = 1000.0


class SolarModuleValidationError(ValueError):
    """Raised when a PV-module catalogue entry is physically invalid."""


def _require_finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SolarModuleValidationError(f"{field_name} must be a number")
    if not math.isfinite(value):
        raise SolarModuleValidationError(f"{field_name} must be finite")


def _require_finite_positive(value: float, field_name: str) -> None:
    _require_finite(value, field_name)
    if value <= 0:
        raise SolarModuleValidationError(f"{field_name} must be greater than zero")


@dataclass(frozen=True, slots=True)
class SolarModule:
    """Manufacturer specification used by preliminary PV analysis.

    The model intentionally contains no pvlib, irradiance-transposition or
    inverter behavior. Those concerns belong to later adapters/use cases.
    """

    manufacturer: str
    model_name: str
    rated_power_w: float
    width_m: float
    height_m: float
    temperature_coefficient_pct_per_c: float
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
                raise SolarModuleValidationError(f"{field_name} must be non-empty text") from error

        _require_finite_positive(self.rated_power_w, "rated_power_w")
        _require_finite_positive(self.width_m, "width_m")
        _require_finite_positive(self.height_m, "height_m")
        _require_finite(self.temperature_coefficient_pct_per_c, "temperature_coefficient_pct_per_c")
        if not 0 < self.efficiency_percent <= 100:
            raise SolarModuleValidationError(
                "rated_power_w, width_m and height_m imply an impossible efficiency "
                f"({self.efficiency_percent:.2f}%); it must be within (0, 100]"
            )

    @property
    def area_m2(self) -> float:
        """Return the module's physical footprint in square metres."""
        return self.width_m * self.height_m

    @property
    def efficiency_percent(self) -> float:
        """Return the STC efficiency implied by power and physical area."""
        return (
            self.rated_power_w / (self.area_m2 * STANDARD_TEST_CONDITIONS_IRRADIANCE_W_PER_M2) * 100
        )


@dataclass(frozen=True, slots=True)
class SolarModuleCatalog:
    """Immutable collection of uniquely identified PV-module models."""

    modules: tuple[SolarModule, ...]

    def __post_init__(self) -> None:
        identifiers = [(m.manufacturer.casefold(), m.model_name.casefold()) for m in self.modules]
        if len(set(identifiers)) != len(identifiers):
            raise SolarModuleValidationError(
                "catalog contains duplicate manufacturer/model entries"
            )

    def find(self, manufacturer: str, model_name: str) -> SolarModule | None:
        """Find a module by case-insensitive manufacturer and model."""
        identifier = (manufacturer.strip().casefold(), model_name.strip().casefold())
        return next(
            (
                module
                for module in self.modules
                if (module.manufacturer.casefold(), module.model_name.casefold()) == identifier
            ),
            None,
        )
