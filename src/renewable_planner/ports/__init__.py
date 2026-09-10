"""Ports implemented by infrastructure adapters."""

from renewable_planner.ports.reporting import AnalysisReportGenerator, AnalysisReportRequest
from renewable_planner.ports.screening import (
    AnalysisRunRepository,
    ProjectRepository,
    SiteRepository,
    SiteScreeningResultRepository,
    SpatialDataLayerProvider,
    SpatialRuleEvaluator,
    SpatialRuleProvider,
)
from renewable_planner.ports.spatial import (
    ConstraintLayerProvider,
    CoordinateReferenceSystemService,
    ScreeningResultRepository,
    SiteBoundaryProvider,
    SpatialOperations,
)
from renewable_planner.ports.wind import (
    AvailableAreaExtractor,
    WindFarmSimulator,
    WindResourceProvider,
)

__all__ = [
    "AnalysisRunRepository",
    "AnalysisReportGenerator",
    "AnalysisReportRequest",
    "AvailableAreaExtractor",
    "ConstraintLayerProvider",
    "CoordinateReferenceSystemService",
    "ProjectRepository",
    "ScreeningResultRepository",
    "SiteRepository",
    "SiteBoundaryProvider",
    "SiteScreeningResultRepository",
    "SpatialDataLayerProvider",
    "SpatialOperations",
    "SpatialRuleEvaluator",
    "SpatialRuleProvider",
    "WindFarmSimulator",
    "WindResourceProvider",
]
