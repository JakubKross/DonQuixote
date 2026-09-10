"""Hourly energy profile model."""

from collections.abc import Sequence
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


def sum_profiles(profiles: Sequence[EnergyProfile], source: str) -> EnergyProfile:
    """Aggregate multiple profiles sharing the same timestamps into one profile.

    Used to combine identical-length per-turbine profiles into a farm-level
    total, for example when summing wake-adjusted or no-wake production.
    """
    if not profiles:
        raise ValueError("profiles must not be empty")
    samples = tuple(
        EnergySample(
            timestamp=profiles[0].samples[index].timestamp,
            power_mw=sum(profile.samples[index].power_mw for profile in profiles),
        )
        for index in range(len(profiles[0].samples))
    )
    return EnergyProfile(samples=samples, source=source)
