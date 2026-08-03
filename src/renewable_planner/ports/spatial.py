"""Outbound ports used by spatial screening use cases."""

from collections.abc import Sequence
from datetime import date
from typing import Protocol, runtime_checkable
from uuid import UUID

from renewable_planner.domain.common import SpatialGeometry
from renewable_planner.domain.constraint_finding import ConstraintFinding
from renewable_planner.domain.crs import CrsDefinition
from renewable_planner.domain.spatial_constraint import SpatialConstraint


@runtime_checkable
class CoordinateReferenceSystemService(Protocol):
    """Resolve coordinate systems and transform library-neutral geometries."""

    def inspect(self, crs: str | None) -> CrsDefinition:
        """Resolve a CRS into a library-neutral definition."""
        ...

    def transform(
        self,
        geometry: SpatialGeometry,
        target_crs: str,
    ) -> SpatialGeometry:
        """Transform geometry to an explicitly selected target CRS."""
        ...


@runtime_checkable
class SiteBoundaryProvider(Protocol):
    """Obtain the boundary of a site selected for analysis."""

    def get_boundary(self, site_id: UUID) -> SpatialGeometry:
        """Return the site boundary or raise an adapter-specific not-found error."""
        ...


@runtime_checkable
class ConstraintLayerProvider(Protocol):
    """Obtain constraint features relevant to a boundary and date."""

    def get_constraints(
        self,
        boundary: SpatialGeometry,
        as_of: date,
    ) -> tuple[SpatialConstraint, ...]:
        """Return an immutable snapshot of applicable spatial constraints."""
        ...


@runtime_checkable
class SpatialOperations(Protocol):
    """Perform geometry operations without exposing a GIS library."""

    def is_valid(self, geometry: SpatialGeometry) -> bool:
        """Return whether geometry is topologically valid."""
        ...

    def repair(self, geometry: SpatialGeometry) -> SpatialGeometry:
        """Repair basic topology errors and return a valid geometry."""
        ...

    def reproject(self, geometry: SpatialGeometry, target_crs: str) -> SpatialGeometry:
        """Return geometry represented in the target coordinate system."""
        ...

    def buffer_meters(
        self,
        geometry: SpatialGeometry,
        distance_meters: float,
    ) -> SpatialGeometry:
        """Return a metric buffer around geometry."""
        ...

    def intersection(
        self,
        left: SpatialGeometry,
        right: SpatialGeometry,
    ) -> SpatialGeometry | None:
        """Return the shared area, or ``None`` when geometries do not intersect."""
        ...

    def difference(
        self,
        left: SpatialGeometry,
        right: SpatialGeometry,
    ) -> SpatialGeometry | None:
        """Subtract right from left, returning ``None`` for an empty result."""
        ...

    def union(self, geometries: Sequence[SpatialGeometry]) -> SpatialGeometry | None:
        """Combine geometries, returning ``None`` for an empty input or result."""
        ...

    def intersects(self, left: SpatialGeometry, right: SpatialGeometry) -> bool:
        """Return whether two geometries share any points."""
        ...

    def area_square_meters(self, geometry: SpatialGeometry) -> float:
        """Return geometry area in square metres."""
        ...


@runtime_checkable
class ScreeningResultRepository(Protocol):
    """Persist findings produced by one screening analysis."""

    def save(
        self,
        analysis_run_id: UUID,
        findings: Sequence[ConstraintFinding],
    ) -> None:
        """Atomically save the findings for an analysis run."""
        ...
