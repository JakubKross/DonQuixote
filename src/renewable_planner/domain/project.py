"""Project aggregate root."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from renewable_planner.domain.common import require_aware, require_non_empty


@dataclass(frozen=True, slots=True)
class Project:
    """Planning project grouping sites and scenarios."""

    name: str
    description: str = ""
    id: UUID = field(default_factory=uuid4)
    site_ids: tuple[UUID, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_non_empty(self.name, "name")
        require_aware(self.created_at, "created_at")
        if len(set(self.site_ids)) != len(self.site_ids):
            raise ValueError("site_ids must not contain duplicates")

    def with_site(self, site_id: UUID) -> "Project":
        """Return the project with a site assigned to it."""
        if site_id in self.site_ids:
            return self
        return replace(self, site_ids=(*self.site_ids, site_id))
