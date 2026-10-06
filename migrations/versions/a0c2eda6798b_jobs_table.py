"""jobs table

Revision ID: a0c2eda6798b
Revises: ec1d81b9a26c
Create Date: 2026-10-06 00:00:00.000000

Applies renewable_planner.adapters.postgres.schema.JOBS_TABLE_SQL verbatim
(Step 3 of docs/WEB_ARCHITECTURE.md: job queue for the async worker). That
constant, not this file, is the source of truth for the DDL — see
schema.py's module docstring for why it is split out from SCHEMA_SQL.
"""

from collections.abc import Sequence

from alembic import op

from renewable_planner.adapters.postgres.schema import JOBS_TABLE_SQL

# revision identifiers, used by Alembic.
revision: str = "a0c2eda6798b"
down_revision: str | Sequence[str] | None = "ec1d81b9a26c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(JOBS_TABLE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS jobs")
