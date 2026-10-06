"""PostGIS-backed adapters (Step 2 of docs/WEB_ARCHITECTURE.md).

See ``repositories`` for the implementations and ``schema`` for the DDL they
depend on. This package is optional (extra ``postgres``) and is never
imported by ``domain/``, ``application/`` or ``ports/``.
"""

from renewable_planner.adapters.postgres.jobs import Job, PostgresJobRepository
from renewable_planner.adapters.postgres.repositories import (
    PostgresAnalysisRunRepository,
    PostgresProjectRepository,
    PostgresScreeningResultRepository,
)
from renewable_planner.adapters.postgres.schema import (
    JOBS_TABLE_SQL,
    SCHEMA_SQL,
    TECHNOLOGY_RESULTS_TABLE_SQL,
)
from renewable_planner.adapters.postgres.technology_results import (
    PostgresTechnologyResultRepository,
)

__all__ = [
    "JOBS_TABLE_SQL",
    "SCHEMA_SQL",
    "TECHNOLOGY_RESULTS_TABLE_SQL",
    "Job",
    "PostgresAnalysisRunRepository",
    "PostgresJobRepository",
    "PostgresProjectRepository",
    "PostgresScreeningResultRepository",
    "PostgresTechnologyResultRepository",
]
