"""Job queue adapter backed by the ``jobs`` table (Step 3 of
docs/WEB_ARCHITECTURE.md).

Not a port used by ``ScreenSite`` — the use case has no idea a queue exists
(see ``renewable_planner.worker``, which calls it directly). This is
infrastructure for the web interface and its worker process only, so unlike
``adapters/postgres/repositories.py`` there is no matching entry in
``ports/``.

``PostgresJobRepository`` is a plain CRUD wrapper: it does not decide
whether a failed job should be retried or given up on — that policy lives in
the worker, which knows ``max_attempts``. ``claim_next`` is the one method
with real logic, because claiming a queued job safely under concurrent
workers needs to be a single atomic statement (``UPDATE ... RETURNING`` over
a ``SELECT ... FOR UPDATE SKIP LOCKED`` subquery) rather than a
read-then-write race.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


@dataclass(frozen=True, slots=True)
class Job:
    """One row of the ``jobs`` table."""

    id: UUID
    job_type: str
    payload: dict[str, Any]
    status: str
    analysis_run_id: UUID | None
    created_at: datetime
    locked_at: datetime | None
    locked_by: str | None
    attempts: int
    last_error: str | None


_COLUMNS = (
    "id, job_type, payload, status, analysis_run_id, created_at, "
    "locked_at, locked_by, attempts, last_error"
)


class PostgresJobRepository:
    """Enqueue, claim and update rows in the ``jobs`` table."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def enqueue(
        self,
        job_id: UUID,
        job_type: str,
        payload: dict[str, Any],
    ) -> Job:
        """Insert a new, queued job and return it."""
        created_at = datetime.now(UTC)
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (id, job_type, payload, status, created_at, attempts)
                VALUES (%(id)s, %(job_type)s, %(payload)s, 'queued', %(created_at)s, 0)
                """,
                {
                    "id": job_id,
                    "job_type": job_type,
                    "payload": Jsonb(payload),
                    "created_at": created_at,
                },
            )
        return Job(
            id=job_id,
            job_type=job_type,
            payload=payload,
            status="queued",
            analysis_run_id=None,
            created_at=created_at,
            locked_at=None,
            locked_by=None,
            attempts=0,
            last_error=None,
        )

    def get(self, job_id: UUID) -> Job | None:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {_COLUMNS} FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
        return None if row is None else _row_to_job(row)

    def claim_next(self, worker_id: str) -> Job | None:
        """Atomically claim the oldest queued job, or return None.

        A single ``UPDATE ... RETURNING`` statement over a
        ``SELECT ... FOR UPDATE SKIP LOCKED`` subquery: the row lock is only
        held for the instant of the update, not for the whole screening run,
        and concurrent workers calling this never claim the same row.
        """
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE jobs SET
                    status = 'running',
                    locked_at = %(locked_at)s,
                    locked_by = %(worker_id)s,
                    attempts = attempts + 1
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE status = 'queued'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING {_COLUMNS}
                """,
                {"locked_at": datetime.now(UTC), "worker_id": worker_id},
            )
            row = cur.fetchone()
        return None if row is None else _row_to_job(row)

    def set_status(
        self,
        job_id: UUID,
        status: str,
        *,
        analysis_run_id: UUID | None = None,
        last_error: str | None = None,
    ) -> None:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs SET
                    status = %(status)s,
                    analysis_run_id = COALESCE(%(analysis_run_id)s, analysis_run_id),
                    last_error = %(last_error)s
                WHERE id = %(id)s
                """,
                {
                    "id": job_id,
                    "status": status,
                    "analysis_run_id": analysis_run_id,
                    "last_error": last_error,
                },
            )


def _row_to_job(row: Any) -> Job:
    (
        job_id,
        job_type,
        payload,
        status,
        analysis_run_id,
        created_at,
        locked_at,
        locked_by,
        attempts,
        last_error,
    ) = row
    return Job(
        id=job_id,
        job_type=job_type,
        payload=payload,
        status=status,
        analysis_run_id=analysis_run_id,
        created_at=created_at,
        locked_at=locked_at,
        locked_by=locked_by,
        attempts=attempts,
        last_error=last_error,
    )


__all__ = ["Job", "PostgresJobRepository"]
