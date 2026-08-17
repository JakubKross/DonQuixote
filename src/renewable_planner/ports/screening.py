"""Ports required by the ScreenSite application use case."""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol, runtime_checkable
from uuid import UUID

from renewable_planner.domain.analysis_run import AnalysisRun
from renewable_planner.domain.common import SpatialGeometry
from renewable_planner.domain.project import Project
from renewable_planner.domain.site import Site
from renewable_planner.domain.spatial_constraint import SpatialConstraint
from renewable_planner.domain.spatial_screening import (
    ScreenSiteResult,
    SpatialDataLayer,
    SpatialRuleEngineResult,
)


@runtime_checkable
class ProjectRepository(Protocol):
    def get(self, project_id: UUID) -> Project | None:
        """Return a project or None when it does not exist."""
        ...


@runtime_checkable
class SiteRepository(Protocol):
    def get(self, site_id: UUID) -> Site | None:
        """Return a site or None when it does not exist."""
        ...


@runtime_checkable
class SpatialRuleProvider(Protocol):
    def get_active(
        self, country: str, technology: str, as_of: date
    ) -> tuple[SpatialConstraint, ...]:
        """Return the active rules for a country and technology."""
        ...


@runtime_checkable
class SpatialDataLayerProvider(Protocol):
    def get_layers(
        self,
        names: Sequence[str],
        boundary: SpatialGeometry,
        as_of: date,
    ) -> tuple[SpatialDataLayer, ...]:
        """Return versioned layer snapshots clipped or relevant to a boundary."""
        ...


@runtime_checkable
class SpatialRuleEvaluator(Protocol):
    def evaluate(
        self,
        site: SpatialGeometry,
        rules: Sequence[SpatialConstraint],
        layers: Mapping[str, SpatialDataLayer],
        technology: str,
        analysis_date: date,
        analysis_run_id: UUID | None = None,
    ) -> SpatialRuleEngineResult:
        """Evaluate rules without exposing a GIS implementation."""
        ...


@runtime_checkable
class AnalysisRunRepository(Protocol):
    def save(self, analysis_run: AnalysisRun) -> None:
        """Create or update an analysis run."""
        ...


@runtime_checkable
class SiteScreeningResultRepository(Protocol):
    def save(self, result: ScreenSiteResult) -> None:
        """Persist the standardized, traceable screening result."""
        ...
