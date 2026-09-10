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
from renewable_planner.domain.energy_profile import EnergyProfile, EnergySample, sum_profiles
from renewable_planner.domain.project import Project
from renewable_planner.domain.scenario import Scenario
from renewable_planner.domain.site import Site
from renewable_planner.domain.solar_layout import (
    GroundCoverageRatio,
    SolarArrayLayout,
    SolarArraySizer,
    SolarLayoutValidationError,
)
from renewable_planner.domain.solar_module import (
    SolarModule,
    SolarModuleCatalog,
    SolarModuleValidationError,
)
from renewable_planner.domain.solar_production import (
    SolarProductionModel,
    SolarProductionValidationError,
)
from renewable_planner.domain.solar_resource import (
    SolarResourceSample,
    SolarResourceTimeSeries,
    SolarResourceValidationError,
)
from renewable_planner.domain.solar_simulation import (
    SolarSimulationRequest,
    SolarSimulationResult,
    SolarSimulationValidationError,
)
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
from renewable_planner.domain.wind_layout import (
    AvailableArea,
    GridTurbineCandidateGenerator,
    TurbinePosition,
    TurbineSpacing,
    WindLayoutValidationError,
)
from renewable_planner.domain.wind_production import (
    WindProductionModel,
    WindProductionValidationError,
)
from renewable_planner.domain.wind_resource import (
    WindResourceSample,
    WindResourceTimeSeries,
    WindResourceValidationError,
)
from renewable_planner.domain.wind_simulation import (
    WindSimulationRequest,
    WindSimulationResult,
    WindSimulationValidationError,
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
    "GroundCoverageRatio",
    "SolarArrayLayout",
    "SolarArraySizer",
    "SolarLayoutValidationError",
    "SolarModule",
    "SolarModuleCatalog",
    "SolarModuleValidationError",
    "SolarProductionModel",
    "SolarProductionValidationError",
    "SolarResourceSample",
    "SolarResourceTimeSeries",
    "SolarResourceValidationError",
    "SolarSimulationRequest",
    "SolarSimulationResult",
    "SolarSimulationValidationError",
    "SpatialConstraint",
    "SpatialDataLayer",
    "SpatialGeometry",
    "SpatialRuleEngineResult",
    "UnrecognizedCoordinateReferenceSystemError",
    "sum_profiles",
    "PowerCurvePoint",
    "WindTurbine",
    "WindTurbineCatalog",
    "WindTurbineValidationError",
    "AvailableArea",
    "GridTurbineCandidateGenerator",
    "TurbinePosition",
    "TurbineSpacing",
    "WindLayoutValidationError",
    "WindProductionModel",
    "WindProductionValidationError",
    "WindResourceSample",
    "WindResourceTimeSeries",
    "WindResourceValidationError",
    "WindSimulationRequest",
    "WindSimulationResult",
    "WindSimulationValidationError",
    "normalize_crs",
]
