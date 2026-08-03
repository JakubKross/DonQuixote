from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from renewable_planner.domain import (
    ConstraintCategory,
    ConstraintFinding,
    FindingStatus,
    SpatialConstraint,
    SpatialGeometry,
)
from renewable_planner.ports import (
    ConstraintLayerProvider,
    ScreeningResultRepository,
    SiteBoundaryProvider,
    SpatialOperations,
)


class InMemoryBoundaryProvider:
    def __init__(self, boundaries: dict[UUID, SpatialGeometry]) -> None:
        self._boundaries = boundaries

    def get_boundary(self, site_id: UUID) -> SpatialGeometry:
        return self._boundaries[site_id]


class InMemoryConstraintLayerProvider:
    def __init__(self, constraints: Sequence[SpatialConstraint]) -> None:
        self._constraints = tuple(constraints)

    def get_constraints(
        self,
        boundary: SpatialGeometry,
        as_of: date,
    ) -> tuple[SpatialConstraint, ...]:
        del boundary
        return tuple(
            constraint
            for constraint in self._constraints
            if constraint.valid_from <= as_of
            and (constraint.valid_to is None or constraint.valid_to >= as_of)
        )


class StubSpatialOperations:
    def is_valid(self, geometry: SpatialGeometry) -> bool:
        return bool(geometry.wkt)

    def repair(self, geometry: SpatialGeometry) -> SpatialGeometry:
        return geometry

    def reproject(self, geometry: SpatialGeometry, target_crs: str) -> SpatialGeometry:
        return SpatialGeometry(wkt=geometry.wkt, crs=target_crs)

    def buffer_meters(
        self,
        geometry: SpatialGeometry,
        distance_meters: float,
    ) -> SpatialGeometry:
        if distance_meters < 0:
            raise ValueError("distance_meters must not be negative")
        return SpatialGeometry(
            wkt=f"BUFFER ({geometry.wkt}, {distance_meters})",
            crs=geometry.crs,
        )

    def intersection(
        self,
        left: SpatialGeometry,
        right: SpatialGeometry,
    ) -> SpatialGeometry | None:
        if left.crs != right.crs:
            raise ValueError("geometries must use the same CRS")
        return left

    def difference(
        self,
        left: SpatialGeometry,
        right: SpatialGeometry,
    ) -> SpatialGeometry | None:
        if left.crs != right.crs:
            raise ValueError("geometries must use the same CRS")
        return left

    def union(self, geometries: Sequence[SpatialGeometry]) -> SpatialGeometry | None:
        return geometries[0] if geometries else None

    def intersects(self, left: SpatialGeometry, right: SpatialGeometry) -> bool:
        return left.crs == right.crs

    def area_square_meters(self, geometry: SpatialGeometry) -> float:
        del geometry
        return 1.0


class InMemoryScreeningResultRepository:
    def __init__(self) -> None:
        self.saved: dict[UUID, tuple[ConstraintFinding, ...]] = {}

    def save(
        self,
        analysis_run_id: UUID,
        findings: Sequence[ConstraintFinding],
    ) -> None:
        self.saved[analysis_run_id] = tuple(findings)


def _geometry(crs: str = "EPSG:2180") -> SpatialGeometry:
    return SpatialGeometry("POLYGON ((0 0, 1 0, 1 1, 0 0))", crs)


def _constraint() -> SpatialConstraint:
    return SpatialConstraint(
        name="Ograniczenie testowe",
        category=ConstraintCategory.TECHNICAL,
        geometry=_geometry(),
        rule_version="test-1",
        source="test fixture",
        valid_from=date(2026, 1, 1),
    )


def test_boundary_provider_contract_and_test_implementation() -> None:
    site_id = uuid4()
    boundary = _geometry()
    provider = InMemoryBoundaryProvider({site_id: boundary})

    assert isinstance(provider, SiteBoundaryProvider)
    assert provider.get_boundary(site_id) == boundary


def test_constraint_provider_returns_applicable_snapshot() -> None:
    constraint = _constraint()
    provider = InMemoryConstraintLayerProvider([constraint])

    assert isinstance(provider, ConstraintLayerProvider)
    assert provider.get_constraints(_geometry(), date(2026, 7, 1)) == (constraint,)
    assert provider.get_constraints(_geometry(), date(2025, 7, 1)) == ()


def test_spatial_operations_contract_keeps_geometry_library_neutral() -> None:
    operations = StubSpatialOperations()
    geometry = _geometry()

    assert isinstance(operations, SpatialOperations)
    assert operations.is_valid(geometry)
    assert operations.repair(geometry) == geometry
    assert operations.reproject(geometry, "EPSG:4326").crs == "EPSG:4326"
    assert operations.buffer_meters(geometry, 500).crs == geometry.crs
    assert operations.intersection(geometry, geometry) == geometry
    assert operations.difference(geometry, geometry) == geometry
    assert operations.union([geometry]) == geometry
    assert operations.intersects(geometry, geometry)
    assert operations.area_square_meters(geometry) == 1.0


def test_screening_repository_saves_immutable_finding_snapshot() -> None:
    analysis_run_id = uuid4()
    finding = ConstraintFinding(
        analysis_run_id=analysis_run_id,
        constraint_id=uuid4(),
        status=FindingStatus.NOT_AFFECTED,
        message="Nie wykryto przecięcia.",
        analyzed_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    repository = InMemoryScreeningResultRepository()

    assert isinstance(repository, ScreeningResultRepository)
    repository.save(analysis_run_id, [finding])

    assert repository.saved[analysis_run_id] == (finding,)
