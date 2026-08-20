"""Public domain model."""

from renewable_planner.domain.analysis_run import AnalysisRun, AnalysisRunStatus
from renewable_planner.domain.common import SpatialGeometry
from renewable_planner.domain.constraint_finding import ConstraintFinding, FindingStatus
from renewable_planner.domain.crs import (
    CoordinateReferenceSystemError,
    CoordinateTransformationError,
    CrsDefinition,
    CrsValidationError,
    MissingCoordinateReferenceSystemError,
    NonMetricCoordinateReferenceSystemError,
    UnrecognizedCoordinateReferenceSystemError,
    normalize_crs,
)
from renewable_planner.domain.energy_profile import EnergyProfile, EnergySample
from renewable_planner.domain.project import Project
from renewable_planner.domain.scenario import Scenario
from renewable_planner.domain.site import Site
from renewable_planner.domain.spatial_constraint import (
    ConstraintCategory,
    ConstraintLevel,
    SpatialConstraint,
)
from renewable_planner.domain.spatial_screening import (
    ScreenSiteResult,
    SpatialDataLayer,
    SpatialRuleEngineResult,
)
from renewable_planner.domain.wind_turbine import (
    PowerCurvePoint,
    WindTurbine,
    WindTurbineCatalog,
    WindTurbineValidationError,
)

__all__ = [
    "AnalysisRun",
    "AnalysisRunStatus",
    "ConstraintCategory",
    "ConstraintLevel",
    "ConstraintFinding",
    "CoordinateReferenceSystemError",
    "CoordinateTransformationError",
    "CrsDefinition",
    "CrsValidationError",
    "EnergyProfile",
    "EnergySample",
    "FindingStatus",
    "MissingCoordinateReferenceSystemError",
    "NonMetricCoordinateReferenceSystemError",
    "Project",
    "Scenario",
    "ScreenSiteResult",
    "Site",
    "SpatialConstraint",
    "SpatialDataLayer",
    "SpatialGeometry",
    "SpatialRuleEngineResult",
    "UnrecognizedCoordinateReferenceSystemError",
    "PowerCurvePoint",
    "WindTurbine",
    "WindTurbineCatalog",
    "WindTurbineValidationError",
    "normalize_crs",
]
