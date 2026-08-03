"""Result of applying a spatial constraint."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from renewable_planner.domain.common import SpatialGeometry, require_aware, require_non_empty


class FindingStatus(StrEnum):
    """Outcome of evaluating a constraint."""

    AFFECTED = "affected"
    NOT_AFFECTED = "not_affected"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class ConstraintFinding:
    """Non-binding, traceable finding produced by an analysis run."""

    analysis_run_id: UUID
    constraint_id: UUID
    status: FindingStatus
    message: str
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    affected_geometry: SpatialGeometry | None = None
    requires_expert_review: bool = True
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        require_non_empty(self.message, "message")
        require_aware(self.analyzed_at, "analyzed_at")
        if self.status is FindingStatus.AFFECTED and self.affected_geometry is None:
            raise ValueError("an affected finding must include affected_geometry")
        if self.status is not FindingStatus.AFFECTED and self.affected_geometry is not None:
            raise ValueError("only an affected finding can include affected_geometry")
