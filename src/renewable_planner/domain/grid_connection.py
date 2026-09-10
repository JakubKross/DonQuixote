"""Domain model for a grid connection point's export limit and curtailment.

This is the independent ``grid`` module referenced by ``AGENTS.md``. It has
no knowledge of wind or solar — it only clips an hourly ``EnergyProfile`` to
a maximum export power. The ``hybrid`` module combines wind and PV profiles
through the shared ``EnergyProfile`` model and then applies this limiter.
"""

import math
from dataclasses import dataclass

from renewable_planner.domain.energy_profile import EnergyProfile, EnergySample


class GridConnectionValidationError(ValueError):
    """Raised when a grid connection limit is invalid."""


@dataclass(frozen=True, slots=True)
class GridConnectionLimit:
    """Maximum instantaneous export power at a connection point."""

    limit_mw: float

    def __post_init__(self) -> None:
        if isinstance(self.limit_mw, bool) or not isinstance(self.limit_mw, (int, float)):
            raise GridConnectionValidationError("limit_mw must be a number")
        if not math.isfinite(self.limit_mw) or self.limit_mw <= 0:
            raise GridConnectionValidationError("limit_mw must be finite and greater than zero")


@dataclass(frozen=True, slots=True)
class CurtailmentResult:
    """Result of clipping a power profile to a grid connection limit."""

    delivered_profile: EnergyProfile
    curtailed_energy_mwh: float
    curtailed_energy_fraction: float
    utilization_fraction: float


class GridConnectionLimiter:
    """Clip an hourly power profile to a grid connection's export limit."""

    def apply(self, profile: EnergyProfile, connection: GridConnectionLimit) -> CurtailmentResult:
        """Return the delivered profile and curtailment/utilization summary."""
        delivered_samples = tuple(
            EnergySample(sample.timestamp, min(sample.power_mw, connection.limit_mw))
            for sample in profile.samples
        )
        delivered_profile = EnergyProfile(
            samples=delivered_samples,
            source=f"{profile.source} (curtailed to grid connection limit)",
        )
        gross_energy_mwh = profile.total_energy_mwh
        delivered_energy_mwh = delivered_profile.total_energy_mwh
        curtailed_energy_mwh = max(0.0, gross_energy_mwh - delivered_energy_mwh)
        curtailed_energy_fraction = (
            curtailed_energy_mwh / gross_energy_mwh if gross_energy_mwh else 0.0
        )
        # Each sample is a one-hour average, so one hour at the limit is
        # exactly ``limit_mw`` MWh of theoretical maximum delivery.
        theoretical_max_mwh = connection.limit_mw * len(profile.samples)
        utilization_fraction = (
            delivered_energy_mwh / theoretical_max_mwh if theoretical_max_mwh else 0.0
        )
        return CurtailmentResult(
            delivered_profile=delivered_profile,
            curtailed_energy_mwh=curtailed_energy_mwh,
            curtailed_energy_fraction=curtailed_energy_fraction,
            utilization_fraction=utilization_fraction,
        )
