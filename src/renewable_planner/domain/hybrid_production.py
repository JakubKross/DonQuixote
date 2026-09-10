"""Domain result of aggregating independent technology profiles for hybrid siting.

Mirrors ``domain.wind_simulation.WindSimulationResult`` and
``domain.solar_simulation.SolarSimulationResult``: a plain result DTO used
by the reporting port, produced by the ``hybrid`` application use case that
combines those two modules' outputs through the shared ``EnergyProfile``
model (see AGENTS.md).
"""

from dataclasses import dataclass

from renewable_planner.domain.energy_profile import EnergyProfile
from renewable_planner.domain.grid_connection import CurtailmentResult


@dataclass(frozen=True, slots=True)
class HybridProductionResult:
    """Aggregate hybrid production before and after the grid connection limit."""

    aggregate_profile: EnergyProfile
    curtailment: CurtailmentResult
