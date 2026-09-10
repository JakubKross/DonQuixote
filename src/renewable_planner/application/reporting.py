"""Application use case for rendering an analysis report."""

from renewable_planner.domain.battery_dispatch import BatteryDispatchResult
from renewable_planner.domain.hybrid_production import HybridProductionResult
from renewable_planner.domain.project import Project
from renewable_planner.domain.solar_simulation import SolarSimulationResult
from renewable_planner.domain.spatial_screening import ScreenSiteResult
from renewable_planner.domain.wind_simulation import WindSimulationResult
from renewable_planner.ports.reporting import AnalysisReportGenerator, AnalysisReportRequest


class GenerateAnalysisReport:
    """Render a completed site-screening result through an output port."""

    def __init__(self, generator: AnalysisReportGenerator) -> None:
        self._generator = generator

    def execute(
        self,
        project: Project,
        result: ScreenSiteResult,
        wind_simulation_result: WindSimulationResult | None = None,
        solar_simulation_result: SolarSimulationResult | None = None,
        hybrid_result: HybridProductionResult | None = None,
        battery_dispatch_result: BatteryDispatchResult | None = None,
    ) -> str:
        """Generate a report for a project and its screening/technology results.

        Every technology result is optional so screening-only reports keep
        working unchanged when no technology simulation has been run yet.
        """
        return self._generator.generate(
            AnalysisReportRequest(
                project=project,
                result=result,
                wind_simulation_result=wind_simulation_result,
                solar_simulation_result=solar_simulation_result,
                hybrid_result=hybrid_result,
                battery_dispatch_result=battery_dispatch_result,
            )
        )
