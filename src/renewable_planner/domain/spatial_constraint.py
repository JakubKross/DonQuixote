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


class ConstraintLevel(StrEnum):
    """Effect a spatial rule has on the analyzed site."""

    EXCLUSION = "exclusion"
    CONDITIONAL = "conditional"
    WARNING = "warning"
    INFORMATION = "information"


@dataclass(frozen=True, slots=True)
class SpatialConstraint:
    """Versioned spatial rule and its area of application."""

    name: str
    category: ConstraintCategory
    geometry: SpatialGeometry | None
    rule_version: str
    source: str
    valid_from: date
    valid_to: date | None = None
    level: ConstraintLevel = ConstraintLevel.WARNING
    technologies: frozenset[str] = field(default_factory=frozenset)
    required_layer: str | None = None
    buffer_meters: float = 0.0
    id: UUID = field(default_factory=uuid4)
    operation: str = "intersects"
    legal_basis: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.name, "name")
        require_non_empty(self.rule_version, "rule_version")
        require_non_empty(self.source, "source")
        normalized_technologies = frozenset(
            technology.strip().lower() for technology in self.technologies
        )
        if any(not technology for technology in normalized_technologies):
            raise ValueError("technologies must not contain empty names")
        object.__setattr__(self, "technologies", normalized_technologies)
        if self.required_layer is not None:
            require_non_empty(self.required_layer, "required_layer")
        elif self.geometry is None:
            raise ValueError("geometry is required when required_layer is not configured")
        if self.buffer_meters < 0:
            raise ValueError("buffer_meters must not be negative")
        require_non_empty(self.operation, "operation")
        if self.legal_basis is not None:
            require_non_empty(self.legal_basis, "legal_basis")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be earlier than valid_from")

    def applies_to(self, technology: str) -> bool:
        """Return whether this rule applies to a normalized technology name."""
        require_non_empty(technology, "technology")
        return not self.technologies or technology.strip().lower() in self.technologies

    def is_active_on(self, analysis_date: date) -> bool:
        """Return whether the rule is valid on the analysis date."""
        return self.valid_from <= analysis_date and (
            self.valid_to is None or analysis_date <= self.valid_to
        )
