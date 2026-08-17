"""Analysis execution record."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from renewable_planner.domain.common import require_aware, require_non_empty


class AnalysisRunStatus(StrEnum):
    """Lifecycle state of an analysis execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SUCCEEDED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    """Traceable execution of an analysis with immutable input snapshots."""

    scenario_id: UUID | None = None
    project_id: UUID | None = None
    site_id: UUID | None = None
    technology: str | None = None
    country: str | None = None
    parameters: tuple[tuple[str, str], ...] = ()
    data_versions: tuple[tuple[str, str], ...] = ()
    id: UUID = field(default_factory=uuid4)
    status: AnalysisRunStatus = AnalysisRunStatus.RUNNING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        for field_name, value in (("technology", self.technology), ("country", self.country)):
            if value is not None:
                require_non_empty(value, field_name)
        self._validate_snapshot(self.parameters, "parameters")
        self._validate_snapshot(self.data_versions, "data_versions")
        if self.started_at is not None:
            require_aware(self.started_at, "started_at")
        if self.status is AnalysisRunStatus.PENDING and self.started_at is not None:
            raise ValueError("a pending analysis cannot have started_at")
        if self.status is not AnalysisRunStatus.PENDING and self.started_at is None:
            raise ValueError("a non-pending analysis must have started_at")
        if self.finished_at is not None:
            require_aware(self.finished_at, "finished_at")
            if self.started_at is not None and self.finished_at < self.started_at:
                raise ValueError("finished_at must not be earlier than started_at")
        if self.status in {AnalysisRunStatus.PENDING, AnalysisRunStatus.RUNNING}:
            if self.finished_at is not None:
                raise ValueError("an unfinished analysis cannot have finished_at")
        elif self.finished_at is None:
            raise ValueError("a finished analysis must have finished_at")
        if self.status is AnalysisRunStatus.FAILED:
            if self.error_message is None:
                raise ValueError("a failed analysis must have an error_message")
            require_non_empty(self.error_message, "error_message")
        elif self.error_message is not None:
            raise ValueError("only a failed analysis can have an error_message")

    def start(self, started_at: datetime | None = None) -> "AnalysisRun":
        """Return a running form of a pending analysis."""
        if self.status is not AnalysisRunStatus.PENDING:
            raise ValueError("only a pending analysis can start")
        return replace(
            self,
            status=AnalysisRunStatus.RUNNING,
            started_at=started_at or datetime.now(UTC),
        )

    def complete(self, finished_at: datetime | None = None) -> "AnalysisRun":
        """Return a completed terminal run."""
        if self.status is not AnalysisRunStatus.RUNNING:
            raise ValueError("only a running analysis can complete")
        return replace(
            self,
            status=AnalysisRunStatus.COMPLETED,
            finished_at=finished_at or datetime.now(UTC),
        )

    def succeed(self, finished_at: datetime | None = None) -> "AnalysisRun":
        """Backward-compatible alias for :meth:`complete`."""
        return self.complete(finished_at)

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

    @staticmethod
    def _validate_snapshot(snapshot: tuple[tuple[str, str], ...], field_name: str) -> None:
        if len({name for name, _ in snapshot}) != len(snapshot):
            raise ValueError(f"{field_name} must not contain duplicate names")
        for name, value in snapshot:
            require_non_empty(name, f"{field_name} name")
            require_non_empty(value, f"{field_name} value")
