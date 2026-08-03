"""Hourly energy profile model."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from renewable_planner.domain.common import require_aware, require_non_empty


@dataclass(frozen=True, slots=True)
class EnergySample:
    """Average power during one hourly interval."""

    timestamp: datetime
    power_mw: float

    def __post_init__(self) -> None:
        require_aware(self.timestamp, "timestamp")
        if self.timestamp.minute or self.timestamp.second or self.timestamp.microsecond:
            raise ValueError("timestamp must be aligned to a full hour")
        if self.power_mw < 0:
            raise ValueError("power_mw must not be negative")


@dataclass(frozen=True, slots=True)
class EnergyProfile:
    """Ordered sequence of contiguous hourly power samples."""

    samples: tuple[EnergySample, ...]
    source: str

    def __post_init__(self) -> None:
        require_non_empty(self.source, "source")
        for previous, current in zip(self.samples, self.samples[1:], strict=False):
            if current.timestamp - previous.timestamp != timedelta(hours=1):
                raise ValueError("samples must be ordered and contiguous hourly values")

    @property
    def total_energy_mwh(self) -> float:
        """Return energy represented by one-hour average-power samples."""
        return sum(sample.power_mw for sample in self.samples)
