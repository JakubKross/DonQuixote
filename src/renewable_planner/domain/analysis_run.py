"""Analysis execution record."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from renewable_planner.domain.common import require_aware, require_non_empty


class AnalysisRunStatus(StrEnum):
    """Lifecycle state of an analysis execution."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    """Traceable execution of an analysis for a scenario."""

    scenario_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: AnalysisRunStatus = AnalysisRunStatus.RUNNING
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        require_aware(self.started_at, "started_at")
        if self.finished_at is not None:
            require_aware(self.finished_at, "finished_at")
            if self.finished_at < self.started_at:
                raise ValueError("finished_at must not be earlier than started_at")
        if self.status is AnalysisRunStatus.RUNNING and self.finished_at is not None:
            raise ValueError("a running analysis cannot have finished_at")
        if self.status is not AnalysisRunStatus.RUNNING and self.finished_at is None:
            raise ValueError("a finished analysis must have finished_at")
        if self.status is AnalysisRunStatus.FAILED:
            if self.error_message is None:
                raise ValueError("a failed analysis must have an error_message")
            require_non_empty(self.error_message, "error_message")
        elif self.error_message is not None:
            raise ValueError("only a failed analysis can have an error_message")

    def succeed(self, finished_at: datetime | None = None) -> "AnalysisRun":
        """Return a successful terminal run."""
        if self.status is not AnalysisRunStatus.RUNNING:
            raise ValueError("only a running analysis can succeed")
        return replace(
            self,
            status=AnalysisRunStatus.SUCCEEDED,
            finished_at=finished_at or datetime.now(UTC),
        )

    def fail(self, error_message: str, finished_at: datetime | None = None) -> "AnalysisRun":
        """Return a failed terminal run."""
        if self.status is not AnalysisRunStatus.RUNNING:
            raise ValueError("only a running analysis can fail")
        return replace(
            self,
            status=AnalysisRunStatus.FAILED,
            finished_at=finished_at or datetime.now(UTC),
            error_message=error_message,
        )
