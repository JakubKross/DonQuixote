"""Shared domain value objects and validation."""

from dataclasses import dataclass
from datetime import datetime

from renewable_planner.domain.crs import normalize_crs


def require_non_empty(value: str, field_name: str) -> None:
    """Require a string containing at least one non-whitespace character."""
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def require_aware(value: datetime, field_name: str) -> None:
    """Require a timezone-aware datetime."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SpatialGeometry:
    """Library-neutral spatial geometry with an explicit coordinate system."""

    wkt: str
    crs: str

    def __post_init__(self) -> None:
        require_non_empty(self.wkt, "wkt")
        object.__setattr__(self, "crs", normalize_crs(self.crs))
