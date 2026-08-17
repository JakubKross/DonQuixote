"""Library-neutral input and output models for spatial screening."""

from dataclasses import dataclass

from renewable_planner.domain.analysis_run import AnalysisRun
from renewable_planner.domain.common import SpatialGeometry, require_non_empty
from renewable_planner.domain.constraint_finding import ConstraintFinding


@dataclass(frozen=True, slots=True)
class SpatialDataLayer:
    """Versioned geometry supplied to one or more spatial rules."""

    name: str
    geometry: SpatialGeometry
    source: str
    version: str

    def __post_init__(self) -> None:
        require_non_empty(self.name, "name")
        require_non_empty(self.source, "source")
        require_non_empty(self.version, "version")


@dataclass(frozen=True, slots=True)
class SpatialRuleEngineResult:
    """Geometry and area summary produced by spatial screening."""

    findings: tuple[ConstraintFinding, ...]
    excluded_geometry: SpatialGeometry | None
    remaining_geometry: SpatialGeometry | None
    initial_area_square_meters: float
    excluded_area_square_meters: float
    available_area_square_meters: float


@dataclass(frozen=True, slots=True)
class ScreenSiteResult:
    """Standard result returned and persisted by the ScreenSite use case."""

    analysis_run: AnalysisRun
    spatial_result: SpatialRuleEngineResult
