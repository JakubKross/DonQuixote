"""SQL schema for the PostGIS adapters (Step 2 of docs/WEB_ARCHITECTURE.md).

``SCHEMA_SQL`` is the single source of truth for the tables these adapters
read and write. The Alembic migration in ``migrations/versions/`` executes it
verbatim for real deployments (so schema history is tracked); tests execute
it directly against an ephemeral testcontainers database, which is faster
and does not require Alembic to be configured just to run a test suite.

Only the tables needed to replace ``adapters.memory_repositories`` (projects,
analysis runs, screening results + their findings) plus the ``jobs`` queue
table (Step 3) are defined here. ``sites``, ``spatial_constraints`` and
``spatial_data_layers`` from the full schema sketch in WEB_ARCHITECTURE.md
are not needed yet: the web API still reads site boundaries and
rule/constraint layers from uploaded files (see
``ports.SpatialRuleProvider``/``SpatialDataLayerProvider``), which stays true
until automatic official data sources are in scope.

``JOBS_TABLE_SQL`` is split out from the rest so the Step 3 Alembic migration
can apply just the new table (incrementally, like a normal migration) while
still sharing the exact same DDL text that ``SCHEMA_SQL`` (and the test
suite, which applies ``SCHEMA_SQL`` directly) uses — one definition, no risk
of the two drifting apart.
"""

_CORE_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    site_ids UUID[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY,
    scenario_id UUID,
    project_id UUID,
    site_id UUID,
    technology TEXT,
    country TEXT,
    parameters JSONB NOT NULL DEFAULT '[]',
    data_versions JSONB NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS screening_results (
    analysis_run_id UUID PRIMARY KEY REFERENCES analysis_runs (id) ON DELETE CASCADE,
    excluded_geometry GEOMETRY,
    excluded_crs TEXT,
    remaining_geometry GEOMETRY,
    remaining_crs TEXT,
    initial_area_m2 DOUBLE PRECISION NOT NULL,
    excluded_area_m2 DOUBLE PRECISION NOT NULL,
    available_area_m2 DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS screening_results_excluded_geometry_gix
    ON screening_results USING GIST (excluded_geometry);
CREATE INDEX IF NOT EXISTS screening_results_remaining_geometry_gix
    ON screening_results USING GIST (remaining_geometry);

CREATE TABLE IF NOT EXISTS constraint_findings (
    id UUID PRIMARY KEY,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs (id) ON DELETE CASCADE,
    constraint_id UUID NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL,
    affected_geometry GEOMETRY,
    affected_crs TEXT,
    level TEXT NOT NULL,
    data_source TEXT NOT NULL,
    data_version TEXT NOT NULL,
    requires_expert_review BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS constraint_findings_analysis_run_id_idx
    ON constraint_findings (analysis_run_id);
CREATE INDEX IF NOT EXISTS constraint_findings_affected_geometry_gix
    ON constraint_findings USING GIST (affected_geometry);
"""

JOBS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY,
    job_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL,
    analysis_run_id UUID REFERENCES analysis_runs (id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL,
    locked_at TIMESTAMPTZ,
    locked_by TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS jobs_status_created_at_idx
    ON jobs (status, created_at);
"""

SCHEMA_SQL = _CORE_SCHEMA_SQL + JOBS_TABLE_SQL
