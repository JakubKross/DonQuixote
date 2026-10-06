"""PostGIS-backed adapters for the ports used by the web API (Step 2 of
docs/WEB_ARCHITECTURE.md).

These implement the exact same three ports/protocols as
:mod:`renewable_planner.adapters.memory_repositories` (``ProjectRepository``
plus ``add``, ``AnalysisRunRepository``/``AnalysisRunQuery``,
``SiteScreeningResultRepository``/``ScreeningResultQuery``), so
``api/app.py`` can swap one set for the other purely through composition —
no route changes. Domain code never imports this module or ``psycopg``;
only ``composition.py`` and ``api/app.py`` wire it in.

A connection is opened per call rather than pooled. At the scale this
project targets ("wstępny screening", not a high-throughput service — see
WEB_ARCHITECTURE.md section 4.3), that is simpler to reason about than
managing pool lifecycle, and avoids adding ``psycopg_pool`` as a dependency
before there is a demonstrated need for it.
"""

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from renewable_planner.domain.analysis_run import AnalysisRun, AnalysisRunStatus
from renewable_planner.domain.common import SpatialGeometry
from renewable_planner.domain.constraint_finding import ConstraintFinding, FindingStatus
from renewable_planner.domain.project import Project
from renewable_planner.domain.spatial_constraint import ConstraintLevel
from renewable_planner.domain.spatial_screening import ScreenSiteResult, SpatialRuleEngineResult


def _srid(crs: str) -> int:
    """Extract the numeric SRID from a canonical ``EPSG:<code>`` identifier."""
    return int(crs.split(":", 1)[1])


def _pairs_to_jsonb(pairs: tuple[tuple[str, str], ...]) -> Jsonb:
    """Wrap an ordered name/value snapshot for a ``jsonb`` column.

    Encoded as a JSON array of ``[name, value]`` pairs (rather than a JSON
    object) to keep insertion order exact on round-trip — ``jsonb`` does not
    guarantee key order for objects. ``Jsonb`` (rather than a manually
    ``json.dumps``-ed plain string) makes psycopg send the value with the
    correct type so PostgreSQL never has to guess it should be jsonb.
    """
    return Jsonb([[name, value] for name, value in pairs])


def _json_to_pairs(value: Any) -> tuple[tuple[str, str], ...]:
    # psycopg decodes jsonb columns to Python objects (list of pairs) by
    # default; the str branch is a defensive fallback in case a driver
    # configuration ever returns the raw JSON text instead.
    data = json.loads(value) if isinstance(value, str) else value
    return tuple((name, val) for name, val in data)


class PostgresProjectRepository:
    """``ProjectRepository`` (plus ``add``) backed by a ``projects`` table."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def add(self, project: Project) -> None:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO projects (id, name, description, site_ids, created_at)
                VALUES (%(id)s, %(name)s, %(description)s, %(site_ids)s, %(created_at)s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    site_ids = EXCLUDED.site_ids,
                    created_at = EXCLUDED.created_at
                """,
                {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "site_ids": list(project.site_ids),
                    "created_at": project.created_at,
                },
            )

    def get(self, project_id: UUID) -> Project | None:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT name, description, site_ids, created_at FROM projects WHERE id = %s",
                (project_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        name, description, site_ids, created_at = row
        return Project(
            id=project_id,
            name=name,
            description=description,
            site_ids=tuple(site_ids),
            created_at=created_at,
        )


class PostgresAnalysisRunRepository:
    """``AnalysisRunRepository`` and ``AnalysisRunQuery`` backed by Postgres."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def save(self, analysis_run: AnalysisRun) -> None:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analysis_runs (
                    id, scenario_id, project_id, site_id, technology, country,
                    parameters, data_versions, status, created_at, started_at,
                    finished_at, error_message
                ) VALUES (
                    %(id)s, %(scenario_id)s, %(project_id)s, %(site_id)s, %(technology)s,
                    %(country)s, %(parameters)s, %(data_versions)s, %(status)s,
                    %(created_at)s, %(started_at)s, %(finished_at)s, %(error_message)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    scenario_id = EXCLUDED.scenario_id,
                    project_id = EXCLUDED.project_id,
                    site_id = EXCLUDED.site_id,
                    technology = EXCLUDED.technology,
                    country = EXCLUDED.country,
                    parameters = EXCLUDED.parameters,
                    data_versions = EXCLUDED.data_versions,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    started_at = EXCLUDED.started_at,
                    finished_at = EXCLUDED.finished_at,
                    error_message = EXCLUDED.error_message
                """,
                {
                    "id": analysis_run.id,
                    "scenario_id": analysis_run.scenario_id,
                    "project_id": analysis_run.project_id,
                    "site_id": analysis_run.site_id,
                    "technology": analysis_run.technology,
                    "country": analysis_run.country,
                    "parameters": _pairs_to_jsonb(analysis_run.parameters),
                    "data_versions": _pairs_to_jsonb(analysis_run.data_versions),
                    "status": analysis_run.status.value,
                    "created_at": analysis_run.created_at,
                    "started_at": analysis_run.started_at,
                    "finished_at": analysis_run.finished_at,
                    "error_message": analysis_run.error_message,
                },
            )

    def get(self, analysis_run_id: UUID) -> AnalysisRun | None:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT scenario_id, project_id, site_id, technology, country,
                       parameters, data_versions, status, created_at, started_at,
                       finished_at, error_message
                FROM analysis_runs WHERE id = %s
                """,
                (analysis_run_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_analysis_run(analysis_run_id, row)


def _row_to_analysis_run(analysis_run_id: UUID, row: Sequence[Any]) -> AnalysisRun:
    (
        scenario_id,
        project_id,
        site_id,
        technology,
        country,
        parameters,
        data_versions,
        status,
        created_at,
        started_at,
        finished_at,
        error_message,
    ) = row
    return AnalysisRun(
        id=analysis_run_id,
        scenario_id=scenario_id,
        project_id=project_id,
        site_id=site_id,
        technology=technology,
        country=country,
        parameters=_json_to_pairs(parameters),
        data_versions=_json_to_pairs(data_versions),
        status=AnalysisRunStatus(status),
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
        error_message=error_message,
    )


class PostgresScreeningResultRepository:
    """``SiteScreeningResultRepository`` and ``ScreeningResultQuery`` backed by
    Postgres.

    ``ScreenSiteResult`` embeds the completed ``AnalysisRun`` it belongs to,
    so reading one back also needs the run — this repository is handed an
    ``AnalysisRunQuery`` (``PostgresAnalysisRunRepository`` in practice) to
    look it up rather than duplicating run fields into this table, keeping
    the run's own table the single source of truth for its fields.
    """

    def __init__(self, dsn: str, analysis_run_query: "PostgresAnalysisRunRepository") -> None:
        self._dsn = dsn
        self._analysis_run_query = analysis_run_query

    def save(self, result: ScreenSiteResult) -> None:
        run_id = result.analysis_run.id
        spatial = result.spatial_result
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            _upsert_screening_result(cur, run_id, spatial)
            # Findings are immutable per run in practice (one screening run
            # produces its findings once), but delete-then-insert makes
            # `save` safe to call again for the same run without leaving
            # stale rows from a previous, different result.
            cur.execute(
                "DELETE FROM constraint_findings WHERE analysis_run_id = %s",
                (run_id,),
            )
            for finding in spatial.findings:
                _insert_finding(cur, finding)

    def get(self, analysis_run_id: UUID) -> ScreenSiteResult | None:
        analysis_run = self._analysis_run_query.get(analysis_run_id)
        if analysis_run is None:
            return None
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT ST_AsText(excluded_geometry), excluded_crs,
                       ST_AsText(remaining_geometry), remaining_crs,
                       initial_area_m2, excluded_area_m2, available_area_m2
                FROM screening_results WHERE analysis_run_id = %s
                """,
                (analysis_run_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            (
                excluded_wkt,
                excluded_crs,
                remaining_wkt,
                remaining_crs,
                initial_area,
                excluded_area,
                available_area,
            ) = row

            cur.execute(
                """
                SELECT id, constraint_id, status, message, analyzed_at,
                       ST_AsText(affected_geometry), affected_crs, level,
                       data_source, data_version, requires_expert_review
                FROM constraint_findings WHERE analysis_run_id = %s
                ORDER BY analyzed_at, id
                """,
                (analysis_run_id,),
            )
            finding_rows = cur.fetchall()

        findings = tuple(_row_to_finding(analysis_run_id, row) for row in finding_rows)
        spatial = SpatialRuleEngineResult(
            findings=findings,
            excluded_geometry=_maybe_geometry(excluded_wkt, excluded_crs),
            remaining_geometry=_maybe_geometry(remaining_wkt, remaining_crs),
            initial_area_square_meters=initial_area,
            excluded_area_square_meters=excluded_area,
            available_area_square_meters=available_area,
        )
        return ScreenSiteResult(analysis_run=analysis_run, spatial_result=spatial)


def _upsert_screening_result(
    cur: "psycopg.Cursor[Any]", run_id: UUID, spatial: SpatialRuleEngineResult
) -> None:
    excluded = spatial.excluded_geometry
    remaining = spatial.remaining_geometry
    cur.execute(
        f"""
        INSERT INTO screening_results (
            analysis_run_id, excluded_geometry, excluded_crs,
            remaining_geometry, remaining_crs,
            initial_area_m2, excluded_area_m2, available_area_m2
        ) VALUES (
            %(run_id)s,
            {"ST_GeomFromText(%(excluded_wkt)s, %(excluded_srid)s)" if excluded else "NULL"},
            %(excluded_crs)s,
            {"ST_GeomFromText(%(remaining_wkt)s, %(remaining_srid)s)" if remaining else "NULL"},
            %(remaining_crs)s,
            %(initial_area)s, %(excluded_area)s, %(available_area)s
        )
        ON CONFLICT (analysis_run_id) DO UPDATE SET
            excluded_geometry = EXCLUDED.excluded_geometry,
            excluded_crs = EXCLUDED.excluded_crs,
            remaining_geometry = EXCLUDED.remaining_geometry,
            remaining_crs = EXCLUDED.remaining_crs,
            initial_area_m2 = EXCLUDED.initial_area_m2,
            excluded_area_m2 = EXCLUDED.excluded_area_m2,
            available_area_m2 = EXCLUDED.available_area_m2
        """,
        {
            "run_id": run_id,
            "excluded_wkt": excluded.wkt if excluded else None,
            "excluded_srid": _srid(excluded.crs) if excluded else None,
            "excluded_crs": excluded.crs if excluded else None,
            "remaining_wkt": remaining.wkt if remaining else None,
            "remaining_srid": _srid(remaining.crs) if remaining else None,
            "remaining_crs": remaining.crs if remaining else None,
            "initial_area": spatial.initial_area_square_meters,
            "excluded_area": spatial.excluded_area_square_meters,
            "available_area": spatial.available_area_square_meters,
        },
    )


def _insert_finding(cur: "psycopg.Cursor[Any]", finding: ConstraintFinding) -> None:
    geometry = finding.affected_geometry
    cur.execute(
        f"""
        INSERT INTO constraint_findings (
            id, analysis_run_id, constraint_id, status, message, analyzed_at,
            affected_geometry, affected_crs, level, data_source, data_version,
            requires_expert_review
        ) VALUES (
            %(id)s, %(run_id)s, %(constraint_id)s, %(status)s, %(message)s,
            %(analyzed_at)s,
            {"ST_GeomFromText(%(wkt)s, %(srid)s)" if geometry else "NULL"},
            %(crs)s, %(level)s, %(data_source)s, %(data_version)s,
            %(requires_expert_review)s
        )
        """,
        {
            "id": finding.id,
            "run_id": finding.analysis_run_id,
            "constraint_id": finding.constraint_id,
            "status": finding.status.value,
            "message": finding.message,
            "analyzed_at": finding.analyzed_at,
            "wkt": geometry.wkt if geometry else None,
            "srid": _srid(geometry.crs) if geometry else None,
            "crs": geometry.crs if geometry else None,
            "level": finding.level.value,
            "data_source": finding.data_source,
            "data_version": finding.data_version,
            "requires_expert_review": finding.requires_expert_review,
        },
    )


def _maybe_geometry(wkt: str | None, crs: str | None) -> SpatialGeometry | None:
    if wkt is None or crs is None:
        return None
    return SpatialGeometry(wkt=wkt, crs=crs)


def _row_to_finding(analysis_run_id: UUID, row: Sequence[Any]) -> ConstraintFinding:
    (
        finding_id,
        constraint_id,
        status,
        message,
        analyzed_at,
        affected_wkt,
        affected_crs,
        level,
        data_source,
        data_version,
        requires_expert_review,
    ) = row
    return ConstraintFinding(
        id=finding_id,
        analysis_run_id=analysis_run_id,
        constraint_id=constraint_id,
        status=FindingStatus(status),
        message=message,
        analyzed_at=analyzed_at,
        affected_geometry=_maybe_geometry(affected_wkt, affected_crs),
        level=ConstraintLevel(level),
        data_source=data_source,
        data_version=data_version,
        requires_expert_review=requires_expert_review,
    )
