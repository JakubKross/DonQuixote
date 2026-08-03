"""Spatial planning constraint model."""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from uuid import UUID, uuid4

from renewable_planner.domain.common import SpatialGeometry, require_non_empty


class ConstraintCategory(StrEnum):
    """High-level origin of a spatial constraint."""

    LEGAL = "legal"
    ENVIRONMENTAL = "environmental"
    TECHNICAL = "technical"


@dataclass(frozen=True, slots=True)
class SpatialConstraint:
    """Versioned spatial rule and its area of application."""

    name: str
    category: ConstraintCategory
    geometry: SpatialGeometry
    rule_version: str
    source: str
    valid_from: date
    valid_to: date | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        require_non_empty(self.name, "name")
        require_non_empty(self.rule_version, "rule_version")
        require_non_empty(self.source, "source")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be earlier than valid_from")
