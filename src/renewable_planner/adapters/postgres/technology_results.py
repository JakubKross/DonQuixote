"""Technology-result store backed by the ``technology_results`` table.

The PostGIS counterpart of
``adapters.memory_repositories.InMemoryTechnologyResultRepository``: one
JSON payload per (analysis run, kind), where kind is ``wind``, ``solar``,
``hybrid`` or ``battery``. Like ``jobs.py`` this is web-interface
infrastructure with no matching port — the technology use cases return
their results and never store them; ``api/app.py`` does.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


class PostgresTechnologyResultRepository:
    """Save, read and delete per-run technology result payloads."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def save(self, analysis_run_id: UUID, kind: str, payload: dict[str, Any]) -> None:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO technology_results (analysis_run_id, kind, payload, updated_at)
                VALUES (%(run_id)s, %(kind)s, %(payload)s, %(updated_at)s)
                ON CONFLICT (analysis_run_id, kind) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    updated_at = EXCLUDED.updated_at
                """,
                {
                    "run_id": analysis_run_id,
                    "kind": kind,
                    "payload": Jsonb(payload),
                    "updated_at": datetime.now(UTC),
                },
            )

    def get(self, analysis_run_id: UUID, kind: str) -> dict[str, Any] | None:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM technology_results WHERE analysis_run_id = %s AND kind = %s",
                (analysis_run_id, kind),
            )
            row = cur.fetchone()
        if row is None:
            return None
        payload: dict[str, Any] = row[0]
        return payload

    def delete(self, analysis_run_id: UUID, kinds: Iterable[str]) -> None:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM technology_results WHERE analysis_run_id = %s AND kind = ANY(%s)",
                (analysis_run_id, list(kinds)),
            )


__all__ = ["PostgresTechnologyResultRepository"]
