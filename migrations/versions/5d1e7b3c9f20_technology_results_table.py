"""technology_results table

Revision ID: 5d1e7b3c9f20
Revises: a0c2eda6798b
Create Date: 2026-10-06 00:00:00.000000

Applies renewable_planner.adapters.postgres.schema.TECHNOLOGY_RESULTS_TABLE_SQL
verbatim (wind/solar/hybrid/battery results of the web API). That constant,
not this file, is the source of truth for the DDL — see schema.py's module
docstring.
"""

from collections.abc import Sequence

from alembic import op

from renewable_planner.adapters.postgres.schema import TECHNOLOGY_RESULTS_TABLE_SQL

# revision identifiers, used by Alembic.
revision: str = "5d1e7b3c9f20"
down_revision: str | Sequence[str] | None = "a0c2eda6798b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(TECHNOLOGY_RESULTS_TABLE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS technology_results")
