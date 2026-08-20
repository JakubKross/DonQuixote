"""Domain models for a basic wind-turbine catalogue."""

import math
from dataclasses import dataclass

from renewable_planner.domain.common import require_non_empty


class WindTurbineValidationError(ValueError):
    """Raised when a wind-turbine catalogue entry is physically invalid."""


def _require_finite_non_negative(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WindTurbineValidationError(f"{field_name} must be a number")
    if not math.isfinite(value) or value < 0:
        raise WindTurbineValidationError(f"{field_name} must be finite and non-negative")


def _require_finite_positive(value: float, field_name: str) -> None:
    _require_finite_non_negative(value, field_name)
    if value <= 0:
        raise WindTurbineValidationError(f"{field_name} must be greater than zero")


@dataclass(frozen=True, slots=True)
class PowerCurvePoint:
    """One point of a simplified power curve.

    Wind speed is expressed in metres per second and power in kilowatts.
    """

    wind_speed_mps: float
    power_kw: float

    def __post_init__(self) -> None:
        _require_finite_non_negative(self.wind_speed_mps, "wind_speed_mps")
        _require_finite_non_negative(self.power_kw, "power_kw")


@dataclass(frozen=True, slots=True)
class WindTurbine:
    """Manufacturer specification used by preliminary wind analysis.

    The model intentionally contains no wake, aeroelastic or manufacturer
    simulation behavior. Those concerns belong to later adapters/use cases.
    """

    manufacturer: str
    model_name: str
    rated_power_kw: float
    rotor_diameter_m: float
    hub_height_m: float
    cut_in_wind_speed_mps: float
    rated_wind_speed_mps: float
    cut_out_wind_speed_mps: float
    power_curve: tuple[PowerCurvePoint, ...]
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
            except (AttributeError, ValueError) as error:
                raise WindTurbineValidationError(f"{field_name} must be non-empty text") from error

        _require_finite_positive(self.rated_power_kw, "rated_power_kw")
        _require_finite_positive(self.rotor_diameter_m, "rotor_diameter_m")
        _require_finite_positive(self.hub_height_m, "hub_height_m")

        _require_finite_non_negative(self.cut_in_wind_speed_mps, "cut_in_wind_speed_mps")
        _require_finite_non_negative(self.rated_wind_speed_mps, "rated_wind_speed_mps")
        _require_finite_non_negative(self.cut_out_wind_speed_mps, "cut_out_wind_speed_mps")
        if not self.cut_in_wind_speed_mps < self.rated_wind_speed_mps < self.cut_out_wind_speed_mps:
            raise WindTurbineValidationError("wind speeds must satisfy cut-in < rated < cut-out")

        if not self.power_curve:
            raise WindTurbineValidationError("power_curve must contain at least one point")
        previous_speed = -1.0
        for point in self.power_curve:
            if not isinstance(point, PowerCurvePoint):
                raise WindTurbineValidationError("power_curve must contain PowerCurvePoint values")
            if point.wind_speed_mps <= previous_speed:
                raise WindTurbineValidationError(
                    "power_curve wind speeds must be strictly increasing"
                )
            if point.power_kw > self.rated_power_kw:
                raise WindTurbineValidationError("power_curve power must not exceed rated_power_kw")
            previous_speed = point.wind_speed_mps


@dataclass(frozen=True, slots=True)
class WindTurbineCatalog:
    """Immutable collection of uniquely identified wind-turbine models."""

    turbines: tuple[WindTurbine, ...]

    def __post_init__(self) -> None:
        identifiers = [(t.manufacturer.casefold(), t.model_name.casefold()) for t in self.turbines]
        if len(set(identifiers)) != len(identifiers):
            raise WindTurbineValidationError(
                "catalog contains duplicate manufacturer/model entries"
            )

    def find(self, manufacturer: str, model_name: str) -> WindTurbine | None:
        """Find a turbine by case-insensitive manufacturer and model."""
        identifier = (manufacturer.strip().casefold(), model_name.strip().casefold())
        return next(
            (
                turbine
                for turbine in self.turbines
                if (turbine.manufacturer.casefold(), turbine.model_name.casefold()) == identifier
            ),
            None,
        )
