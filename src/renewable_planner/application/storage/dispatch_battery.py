"""DispatchBattery application use case."""

from dataclasses import dataclass

from renewable_planner.domain.battery import Battery
from renewable_planner.domain.battery_dispatch import BatteryDispatcher, BatteryDispatchResult
from renewable_planner.domain.energy_profile import EnergyProfile


@dataclass(frozen=True, slots=True)
class DispatchBatteryCommand:
    """Validated input for simulating one battery against a power profile."""

    profile: EnergyProfile
    battery: Battery
    target_power_mw: float
    initial_state_of_charge_fraction: float


class DispatchBattery:
    """Thin wrapper exposing ``BatteryDispatcher`` as a use case.

    Kept independent of ``wind``, ``solar`` and ``grid``: it only takes an
    ``EnergyProfile`` and a plain target power. Deciding which profile
    (e.g. a hybrid aggregate) and which target (e.g. a grid connection
    limit) to pass in is the caller's — typically the CLI's or a future
    ``hybrid`` orchestration's — responsibility.
    """

    def __init__(self, dispatcher: BatteryDispatcher | None = None) -> None:
        self._dispatcher = dispatcher or BatteryDispatcher()

    def execute(self, command: DispatchBatteryCommand) -> BatteryDispatchResult:
        """Simulate hourly battery dispatch against the given profile."""
        return self._dispatcher.simulate(
            command.battery,
            command.profile,
            command.target_power_mw,
            command.initial_state_of_charge_fraction,
        )
