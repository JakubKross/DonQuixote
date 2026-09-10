"""Domain model for a versioned hourly solar-resource time series."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from renewable_planner.domain.common import require_aware, require_non_empty


class SolarResourceValidationError(ValueError):
    """Raised when a solar-resource time series is invalid."""


def _require_finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SolarResourceValidationError(f"{field_name} must be a number")
    if not math.isfinite(value):
        raise SolarResourceValidationError(f"{field_name} must be finite")


@dataclass(frozen=True, slots=True)
class SolarResourceSample:
    """One hourly plane-of-array irradiance and ambient-temperature observation."""

    timestamp: datetime
    poa_irradiance_w_per_m2: float
    ambient_temperature_c: float

    def __post_init__(self) -> None:
        try:
            require_aware(self.timestamp, "timestamp")
        except ValueError as error:
            raise SolarResourceValidationError(str(error)) from error
        if self.timestamp.minute or self.timestamp.second or self.timestamp.microsecond:
            raise SolarResourceValidationError("timestamp must be aligned to a full hour")

        _require_finite(self.poa_irradiance_w_per_m2, "poa_irradiance_w_per_m2")
        if self.poa_irradiance_w_per_m2 < 0:
            raise SolarResourceValidationError("poa_irradiance_w_per_m2 must be non-negative")

        _require_finite(self.ambient_temperature_c, "ambient_temperature_c")


@dataclass(frozen=True, slots=True)
class SolarResourceTimeSeries:
    """Ordered, contiguous hourly solar observations with data provenance.

    Mirrors ``domain.wind_resource.WindResourceTimeSeries`` for the
    independent ``solar`` module: the same contiguous-hourly-sample rule as
    ``EnergyProfile`` so the series can already be trusted by
    ``SolarProductionModel`` without further validation. Irradiance is
    plane-of-array (POA) — already transposed to the array's tilt and
    orientation — since this module does not perform solar-position or
    transposition calculations.
    """

    samples: tuple[SolarResourceSample, ...]
    source: str
    version: str

    def __post_init__(self) -> None:
        for text, field_name in ((self.source, "source"), (self.version, "version")):
            try:
                require_non_empty(text, field_name)
            except ValueError as error:
                raise SolarResourceValidationError(str(error)) from error
        if not self.samples:
            raise SolarResourceValidationError("samples must not be empty")
        for previous, current in zip(self.samples, self.samples[1:], strict=False):
            if current.timestamp - previous.timestamp != timedelta(hours=1):
                raise SolarResourceValidationError(
                    "samples must be ordered and contiguous hourly values"
                )

    @property
    def timestamps(self) -> tuple[datetime, ...]:
        """Return the hourly timestamps of every sample, in order."""
        return tuple(sample.timestamp for sample in self.samples)

    @property
    def poa_irradiance_w_per_m2(self) -> tuple[float, ...]:
        """Return the plane-of-array irradiance of every sample, in order."""
        return tuple(sample.poa_irradiance_w_per_m2 for sample in self.samples)

    @property
    def ambient_temperature_c(self) -> tuple[float, ...]:
        """Return the ambient temperature of every sample, in order."""
        return tuple(sample.ambient_temperature_c for sample in self.samples)
