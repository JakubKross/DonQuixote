"""Ports for generating reports from completed analyses."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from renewable_planner.domain.project import Project
from renewable_planner.domain.spatial_screening import ScreenSiteResult


@dataclass(frozen=True, slots=True)
class AnalysisReportRequest:
    """Input required by any analysis report renderer."""

    project: Project
    result: ScreenSiteResult


@runtime_checkable
class AnalysisReportGenerator(Protocol):
    """Render a screening result without prescribing an output format."""

    def generate(self, request: AnalysisReportRequest) -> str:
        """Return the rendered report contents."""
        ...
