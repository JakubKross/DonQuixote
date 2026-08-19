"""Application use case for rendering an analysis report."""

from renewable_planner.domain.project import Project
from renewable_planner.domain.spatial_screening import ScreenSiteResult
from renewable_planner.ports.reporting import AnalysisReportGenerator, AnalysisReportRequest


class GenerateAnalysisReport:
    """Render a completed site-screening result through an output port."""

    def __init__(self, generator: AnalysisReportGenerator) -> None:
        self._generator = generator

    def execute(self, project: Project, result: ScreenSiteResult) -> str:
        """Generate a report for a project and its screening result."""
        return self._generator.generate(AnalysisReportRequest(project=project, result=result))
