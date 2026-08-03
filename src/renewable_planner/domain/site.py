"""Analyzed site model."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from renewable_planner.domain.common import SpatialGeometry, require_non_empty


@dataclass(frozen=True, slots=True)
class Site:
    """Geographic area considered by a planning project."""

    name: str
    boundary: SpatialGeometry
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        require_non_empty(self.name, "name")
