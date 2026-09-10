"""AggregateHybridProduction application use case."""

from dataclasses import dataclass

from renewable_planner.domain.energy_profile import EnergyProfile, sum_profiles
from renewable_planner.domain.grid_connection import GridConnectionLimit, GridConnectionLimiter
from renewable_planner.domain.hybrid_production import HybridProductionResult


@dataclass(frozen=True, slots=True)
class AggregateHybridProductionCommand:
    """Hourly production profiles from independent technology modules.

    Every profile must already share the exact same, contiguous hourly
    timestamps (e.g. a wind module's wake-adjusted AC profile and a solar
    module's inverter AC profile computed over the same period). Combining
    them like this is exactly the aggregation the ``hybrid`` module is
    allowed to perform through the shared ``EnergyProfile`` domain model
    (see AGENTS.md) — it does not re-derive wind or solar production logic.
    """

    profiles: tuple[EnergyProfile, ...]
    connection_limit: GridConnectionLimit

    def __post_init__(self) -> None:
        if not self.profiles:
            raise ValueError("at least one production profile is required")
        reference_timestamps = tuple(sample.timestamp for sample in self.profiles[0].samples)
        for index, profile in enumerate(self.profiles[1:], start=1):
            timestamps = tuple(sample.timestamp for sample in profile.samples)
            if timestamps != reference_timestamps:
                raise ValueError(
                    f"profiles[{index}] does not share the same timestamps as profiles[0]"
                )


class AggregateHybridProduction:
    """Combine independent technology profiles and apply a grid connection limit."""

    def __init__(self, limiter: GridConnectionLimiter | None = None) -> None:
        self._limiter = limiter or GridConnectionLimiter()

    def execute(self, command: AggregateHybridProductionCommand) -> HybridProductionResult:
        """Aggregate the given profiles and curtail the total to the grid limit."""
        aggregate_profile = sum_profiles(command.profiles, source="hybrid aggregate (wind + PV)")
        curtailment = self._limiter.apply(aggregate_profile, command.connection_limit)
        return HybridProductionResult(aggregate_profile=aggregate_profile, curtailment=curtailment)
