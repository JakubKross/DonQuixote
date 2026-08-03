"""Planning scenario model."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from renewable_planner.domain.common import require_aware, require_non_empty


@dataclass(frozen=True, slots=True)
class Scenario:
    """A comparable set of assumptions for one project site."""

    project_id: UUID
    site_id: UUID
    name: str
    description: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_non_empty(self.name, "name")
        require_aware(self.created_at, "created_at")
