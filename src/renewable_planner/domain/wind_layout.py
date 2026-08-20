"""Deterministic preliminary turbine-candidate generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypeAlias

Coordinate: TypeAlias = tuple[float, float]


class WindLayoutValidationError(ValueError):
    """Raised when a wind-layout input is invalid."""


def _finite_positive(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WindLayoutValidationError(f"{name} must be a number")
    if not math.isfinite(value) or value <= 0:
        raise WindLayoutValidationError(f"{name} must be finite and greater than zero")
    return float(value)


def _validate_ring(ring: tuple[Coordinate, ...], name: str) -> None:
    if len(ring) < 3:
        raise WindLayoutValidationError(f"{name} must contain at least three points")
    for point in ring:
        if len(point) != 2 or any(not isinstance(value, (int, float)) for value in point):
            raise WindLayoutValidationError(f"{name} must contain coordinate pairs")
        if any(not math.isfinite(value) for value in point):
            raise WindLayoutValidationError(f"{name} coordinates must be finite")
    area = sum(
        ring[index][0] * ring[(index + 1) % len(ring)][1]
        - ring[(index + 1) % len(ring)][0] * ring[index][1]
        for index in range(len(ring))
    )
    if math.isclose(area, 0.0):
        raise WindLayoutValidationError(f"{name} must enclose a non-zero area")


@dataclass(frozen=True, slots=True)
class AvailableArea:
    """A metric polygon available for preliminary turbine placement."""

    exterior: tuple[Coordinate, ...]
    holes: tuple[tuple[Coordinate, ...], ...] = ()

    def __post_init__(self) -> None:
        _validate_ring(self.exterior, "exterior")
        for index, hole in enumerate(self.holes):
            _validate_ring(hole, f"hole {index}")

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        points = self.exterior
        return (
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        )

    def contains(self, point: Coordinate) -> bool:
        """Return whether a point is inside or on the boundary, excluding holes."""
        if not _point_in_ring_or_boundary(point, self.exterior):
            return False
        return not any(_point_in_ring_or_boundary(point, hole) for hole in self.holes)


@dataclass(frozen=True, slots=True)
class TurbineSpacing:
    """Minimum centre-to-centre distance between turbines, in metres."""

    distance_m: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "distance_m", _finite_positive(self.distance_m, "distance_m"))

    @classmethod
    def from_rotor_diameters(cls, multiplier: float, rotor_diameter_m: float) -> TurbineSpacing:
        multiplier = _finite_positive(multiplier, "multiplier")
        rotor_diameter_m = _finite_positive(rotor_diameter_m, "rotor_diameter_m")
        return cls(multiplier * rotor_diameter_m)


@dataclass(frozen=True, slots=True)
class TurbinePosition:
    """Candidate turbine centre in metric coordinates."""

    x_m: float
    y_m: float

    def __post_init__(self) -> None:
        for value, name in ((self.x_m, "x_m"), (self.y_m, "y_m")):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise WindLayoutValidationError(f"{name} must be a finite number")
        object.__setattr__(self, "x_m", float(self.x_m))
        object.__setattr__(self, "y_m", float(self.y_m))


class GridTurbineCandidateGenerator:
    """Generate a stable row-major grid and enforce centre-to-centre spacing."""

    def generate(
        self,
        area: AvailableArea,
        spacing: TurbineSpacing,
        *,
        grid_spacing_m: float | None = None,
    ) -> tuple[TurbinePosition, ...]:
        if not isinstance(area, AvailableArea):
            raise WindLayoutValidationError("area must be an AvailableArea")
        if not isinstance(spacing, TurbineSpacing):
            raise WindLayoutValidationError("spacing must be a TurbineSpacing")
        grid_step = (
            spacing.distance_m
            if grid_spacing_m is None
            else _finite_positive(grid_spacing_m, "grid_spacing_m")
        )
        min_x, min_y, max_x, max_y = area.bounds
        candidates: list[TurbinePosition] = []
        row_count = math.floor((max_y - min_y) / grid_step + 1e-12)
        column_count = math.floor((max_x - min_x) / grid_step + 1e-12)
        for row in range(row_count + 1):
            y = min_y + row * grid_step
            for column in range(column_count + 1):
                x = min_x + column * grid_step
                if area.contains((x, y)) and _has_minimum_distance(
                    (x, y), candidates, spacing.distance_m
                ):
                    candidates.append(TurbinePosition(x, y))
        return tuple(candidates)


def _has_minimum_distance(
    point: Coordinate, accepted: list[TurbinePosition], minimum_distance_m: float
) -> bool:
    minimum_squared = minimum_distance_m * minimum_distance_m
    return all(
        (point[0] - candidate.x_m) ** 2 + (point[1] - candidate.y_m) ** 2 >= minimum_squared - 1e-9
        for candidate in accepted
    )


def _point_in_ring_or_boundary(point: Coordinate, ring: tuple[Coordinate, ...]) -> bool:
    x, y = point
    inside = False
    for index, (start_x, start_y) in enumerate(ring):
        end_x, end_y = ring[(index + 1) % len(ring)]
        cross = (x - start_x) * (end_y - start_y) - (y - start_y) * (end_x - start_x)
        if (
            math.isclose(cross, 0.0, abs_tol=1e-9)
            and min(start_x, end_x) - 1e-9 <= x <= max(start_x, end_x) + 1e-9
            and min(start_y, end_y) - 1e-9 <= y <= max(start_y, end_y) + 1e-9
        ):
            return True
        if (start_y > y) != (end_y > y):
            intersection_x = (end_x - start_x) * (y - start_y) / (end_y - start_y) + start_x
            if x < intersection_x:
                inside = not inside
    return inside
