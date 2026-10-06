"""PostGIS-backed adapters (Step 2 of docs/WEB_ARCHITECTURE.md).

See ``repositories`` for the implementations and ``schema`` for the DDL they
depend on. This package is optional (extra ``postgres``) and is never
imported by ``domain/``, ``application/`` or ``ports/``.
"""

from renewable_planner.adapters.postgres.repositories import (
    PostgresAnalysisRunRepository,
    PostgresProjectRepository,
    PostgresScreeningResultRepository,
)
from renewable_planner.adapters.postgres.schema import SCHEMA_SQL

__all__ = [
    "SCHEMA_SQL",
    "PostgresAnalysisRunRepository",
    "PostgresProjectRepository",
    "PostgresScreeningResultRepository",
]
