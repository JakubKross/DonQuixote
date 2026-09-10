"""Domain model for a versioned hourly wind-resource time series."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from renewable_planner.domain.common import require_aware, require_non_empty


class WindResourceValidationError(ValueError):
    """Raised when a wind-resource time series is invalid."""


def _require_finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WindResourceValidationError(f"{field_name} must be a number")
    if not math.isfinite(value):
        raise WindResourceValidationError(f"{field_name} must be finite")


@dataclass(frozen=True, slots=True)
class WindResourceSample:
    """One hourly wind-speed and direction observation."""

    timestamp: datetime
    wind_speed_mps: float
    wind_direction_deg: float

    def __post_init__(self) -> None:
        try:
            require_aware(self.timestamp, "timestamp")
        except ValueError as error:
            raise WindResourceValidationError(str(error)) from error
        if self.timestamp.minute or self.timestamp.second or self.timestamp.microsecond:
            raise WindResourceValidationError("timestamp must be aligned to a full hour")

        _require_finite(self.wind_speed_mps, "wind_speed_mps")
        if self.wind_speed_mps < 0:
            raise WindResourceValidationError("wind_speed_mps must be non-negative")

        _require_finite(self.wind_direction_deg, "wind_direction_deg")
        if not 0 <= self.wind_direction_deg < 360:
            raise WindResourceValidationError("wind_direction_deg must be within [0, 360)")


@dataclass(frozen=True, slots=True)
class WindResourceTimeSeries:
    """Ordered, contiguous hourly wind observations with data provenance.

    The series intentionally mirrors :class:`~renewable_planner.domain.
    energy_profile.EnergyProfile`'s contiguous-hourly-sample rule so that the
    same input shape can already be trusted by ``WindProductionModel`` and
    ``WindSimulationRequest`` without further validation.
    """

    samples: tuple[WindResourceSample, ...]
    source: str
    version: str

    def __post_init__(self) -> None:
        for text, field_name in ((self.source, "source"), (self.version, "version")):
            try:
                require_non_empty(text, field_name)
            except ValueError as error:
                raise WindResourceValidationError(str(error)) from error
        if not self.samples:
            raise WindResourceValidationError("samples must not be empty")
        for previous, current in zip(self.samples, self.samples[1:], strict=False):
            if current.timestamp - previous.timestamp != timedelta(hours=1):
                raise WindResourceValidationError(
                    "samples must be ordered and contiguous hourly values"
                )

    @property
    def timestamps(self) -> tuple[datetime, ...]:
        """Return the hourly timestamps of every sample, in order."""
        return tuple(sample.timestamp for sample in self.samples)

    @property
    def wind_speeds_mps(self) -> tuple[float, ...]:
        """Return the wind speed of every sample, in order."""
        return tuple(sample.wind_speed_mps for sample in self.samples)

    @property
    def wind_directions_deg(self) -> tuple[float, ...]:
        """Return the wind direction of every sample, in order."""
        return tuple(sample.wind_direction_deg for sample in self.samples)
