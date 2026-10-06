"""initial schema

Revision ID: ec1d81b9a26c
Revises:
Create Date: 2026-09-10 13:27:01.677801

Applies renewable_planner.adapters.postgres.schema.SCHEMA_SQL verbatim —
that constant, not this file, is the source of truth for the DDL. See its
module docstring for which tables exist and why. Tests apply the same
constant directly against an ephemeral testcontainers database rather than
running this migration, so both paths always agree with each other by
construction (there is only one DDL string to drift from).
"""

from collections.abc import Sequence

from alembic import op

from renewable_planner.adapters.postgres.schema import SCHEMA_SQL

# revision identifiers, used by Alembic.
revision: str = "ec1d81b9a26c"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(SCHEMA_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS constraint_findings")
    op.execute("DROP TABLE IF EXISTS screening_results")
    op.execute("DROP TABLE IF EXISTS analysis_runs")
    op.execute("DROP TABLE IF EXISTS projects")
    # The postgis extension is intentionally left installed — other
    # databases/schemas in the same cluster may depend on it, and
    # `CREATE EXTENSION IF NOT EXISTS` in upgrade() makes re-running safe.
