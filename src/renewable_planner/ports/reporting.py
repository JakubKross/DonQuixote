"""Ports for generating reports from completed analyses."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from renewable_planner.domain.battery_dispatch import BatteryDispatchResult
from renewable_planner.domain.hybrid_production import HybridProductionResult
from renewable_planner.domain.project import Project
from renewable_planner.domain.solar_simulation import SolarSimulationResult
from renewable_planner.domain.spatial_screening import ScreenSiteResult
from renewable_planner.domain.wind_simulation import WindSimulationResult


@dataclass(frozen=True, slots=True)
class AnalysisReportRequest:
    """Input required by any analysis report renderer."""

    project: Project
    result: ScreenSiteResult
    wind_simulation_result: WindSimulationResult | None = None
    solar_simulation_result: SolarSimulationResult | None = None
    hybrid_result: HybridProductionResult | None = None
    battery_dispatch_result: BatteryDispatchResult | None = None


@runtime_checkable
class AnalysisReportGenerator(Protocol):
    """Render a screening result without prescribing an output format."""

    def generate(self, request: AnalysisReportRequest) -> str:
        """Return the rendered report contents."""
        ...
