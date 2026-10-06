"""Job worker for asynchronous screenings (Step 3 of docs/WEB_ARCHITECTURE.md).

Polls the ``jobs`` table (``adapters.postgres.jobs.PostgresJobRepository``)
for queued screening jobs and runs them by calling the exact same
``ScreenSite`` use case the synchronous web API (and CLI, and Streamlit) call
— no use-case or domain change was needed for this step, per
docs/WEB_ARCHITECTURE.md section 4.2. A job and the ``AnalysisRun`` it
eventually produces have different ids (``ScreenSite.execute`` always mints
its own); the job row's ``analysis_run_id`` column is what links them, and
``api/app.py`` resolves one from the other when a client polls by job id.

Run with:

    DATABASE_URL=postgresql://user:pass@host/db python -m renewable_planner.worker
"""

from __future__ import annotations

import os
import socket
import time
import uuid
from datetime import date
from pathlib import Path

from renewable_planner.adapters.geospatial.file_screening import load_site
from renewable_planner.adapters.postgres import (
    Job,
    PostgresAnalysisRunRepository,
    PostgresJobRepository,
    PostgresProjectRepository,
    PostgresScreeningResultRepository,
)
from renewable_planner.application.spatial import (
    ScreeningExecutionError,
    ScreenSiteCommand,
    ScreenSiteError,
)
from renewable_planner.composition import build_file_screen_site

DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_MAX_ATTEMPTS = 3


def run_worker(
    dsn: str,
    *,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    worker_id: str | None = None,
    max_iterations: int | None = None,
) -> None:
    """Claim and process queued jobs until ``max_iterations`` is reached.

    ``max_iterations`` is ``None`` (run forever) in production; tests pass a
    finite number so the loop terminates on its own.
    """
    jobs = PostgresJobRepository(dsn)
    projects = PostgresProjectRepository(dsn)
    runs = PostgresAnalysisRunRepository(dsn)
    results = PostgresScreeningResultRepository(dsn, runs)
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"

    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        job = jobs.claim_next(worker_id)
        if job is None:
            time.sleep(poll_interval)
            continue
        _process_job(job, jobs, projects, runs, results, max_attempts=max_attempts)


def _process_job(
    job: Job,
    jobs: PostgresJobRepository,
    projects: PostgresProjectRepository,
    runs: PostgresAnalysisRunRepository,
    results: PostgresScreeningResultRepository,
    *,
    max_attempts: int,
) -> None:
    try:
        analysis_run_id = _execute_screening_job(job, projects, runs, results)
    except ScreeningExecutionError as error:
        _retry_or_fail(job, jobs, max_attempts, str(error), error.analysis_run_id)
    except Exception as error:  # noqa: BLE001 - any failure must not crash the worker loop
        _retry_or_fail(job, jobs, max_attempts, str(error), None)
    else:
        jobs.set_status(job.id, "done", analysis_run_id=analysis_run_id)


def _execute_screening_job(
    job: Job,
    projects: PostgresProjectRepository,
    runs: PostgresAnalysisRunRepository,
    results: PostgresScreeningResultRepository,
) -> uuid.UUID:
    payload = job.payload
    project_id = uuid.UUID(payload["project_id"])
    project = projects.get(project_id)
    if project is None:
        raise ScreenSiteError(f"project {project_id} was not found for job {job.id}")

    site_path = Path(payload["site_path"])
    site = load_site(site_path)
    use_case, _ = build_file_screen_site(
        site,
        site_path,
        Path(payload["constraints_path"]),
        Path(payload["rules_path"]),
        project=project,
        analysis_run_repository=runs,
        result_repository=results,
    )
    command = ScreenSiteCommand(
        project_id=project_id,
        site_id=uuid.UUID(payload["site_id"]),
        country=payload["country"],
        technology=payload["technology"],
        analysis_date=date.fromisoformat(payload["analysis_date"]),
    )
    result = use_case.execute(command)
    return result.analysis_run.id


def _retry_or_fail(
    job: Job,
    jobs: PostgresJobRepository,
    max_attempts: int,
    error_message: str,
    analysis_run_id: uuid.UUID | None,
) -> None:
    status = "queued" if job.attempts < max_attempts else "failed"
    jobs.set_status(
        job.id,
        status,
        analysis_run_id=analysis_run_id,
        last_error=error_message,
    )


def main() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL must be set to run the worker")
    run_worker(dsn)


if __name__ == "__main__":
    main()
