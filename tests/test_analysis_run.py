from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from renewable_planner.domain import AnalysisRun, AnalysisRunStatus


def test_running_analysis_can_succeed() -> None:
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    finished_at = started_at + timedelta(minutes=5)
    run = AnalysisRun(scenario_id=uuid4(), started_at=started_at)

    completed = run.succeed(finished_at)

    assert completed.status is AnalysisRunStatus.SUCCEEDED
    assert completed.finished_at == finished_at


def test_failed_analysis_requires_message() -> None:
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="error_message"):
        AnalysisRun(
            scenario_id=uuid4(),
            status=AnalysisRunStatus.FAILED,
            started_at=started_at,
            finished_at=started_at + timedelta(seconds=1),
        )


def test_finished_analysis_cannot_finish_before_start() -> None:
    started_at = datetime(2026, 1, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="earlier"):
        AnalysisRun(
            scenario_id=uuid4(),
            status=AnalysisRunStatus.SUCCEEDED,
            started_at=started_at,
            finished_at=started_at - timedelta(seconds=1),
        )
