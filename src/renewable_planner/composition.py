"""Shared composition helpers for file-driven interfaces (CLI, Streamlit, API).

Every interface that reads a site boundary, constraint layers and rules from
files needs the exact same wiring of adapters into the ``ScreenSite`` use
case. Defining that wiring once here means no interface has to duplicate
screening logic or composition — each one only supplies file paths.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from renewable_planner.adapters.geospatial.file_screening import (
    FileProjectRepository,
    FileSiteRepository,
    GeoJsonConstraintLayerProvider,
    JsonResultRepository,
    MemoryAnalysisRunRepository,
    YamlSpatialRuleProvider,
    build_project,
)
from renewable_planner.adapters.geospatial.geopandas_spatial_operations import (
    GeoPandasSpatialOperations,
)
from renewable_planner.adapters.geospatial.pyproj_crs_service import (
    PyprojCoordinateReferenceSystemService,
)
from renewable_planner.adapters.reporting import TextAnalysisReportGenerator
from renewable_planner.application.reporting import GenerateAnalysisReport
from renewable_planner.application.spatial import ScreenSite, SpatialRuleEngine
from renewable_planner.domain.project import Project
from renewable_planner.domain.site import Site
from renewable_planner.ports.screening import AnalysisRunRepository, SiteScreeningResultRepository

if TYPE_CHECKING:
    from renewable_planner.adapters.postgres import (
        PostgresAnalysisRunRepository,
        PostgresJobRepository,
        PostgresProjectRepository,
        PostgresScreeningResultRepository,
    )


def build_file_screen_site(
    site: Site,
    site_path: Path,
    constraints_path: Path,
    rules_path: Path,
    *,
    project: Project | None = None,
    analysis_run_repository: AnalysisRunRepository | None = None,
    result_repository: SiteScreeningResultRepository | None = None,
) -> tuple[ScreenSite, Project]:
    """Wire a ``ScreenSite`` use case to file-based adapters.

    Returns the use case together with the ``Project`` it was wired for, so
    the caller can pass both into ``ScreenSiteCommand`` and into report
    generation without re-deriving them.

    ``analysis_run_repository`` and ``result_repository`` default to
    throwaway, one-shot in-memory adapters — right for the CLI and Streamlit,
    which run one screening per process and never look it up again. The web
    API passes in process-shared adapters instead (see
    ``adapters.memory_repositories``) so a run created by one request can be
    read back by a later one.

    ``project`` defaults to ``None``, in which case a fresh ``Project`` is
    built from ``site``/``site_path`` (today's behaviour for CLI, Streamlit
    and the synchronous web API). The worker (Step 3 of
    docs/WEB_ARCHITECTURE.md) passes in the project already persisted at
    enqueue time instead, so it wires the use case to the same project id
    rather than minting a new one.
    """
    project = project or build_project(site, site_path)
    use_case = ScreenSite(
        project_repository=FileProjectRepository(project),
        site_repository=FileSiteRepository(site),
        rule_provider=YamlSpatialRuleProvider(rules_path),
        layer_provider=GeoJsonConstraintLayerProvider(constraints_path, site.boundary.crs),
        rule_evaluator=SpatialRuleEngine(
            GeoPandasSpatialOperations(PyprojCoordinateReferenceSystemService())
        ),
        analysis_run_repository=analysis_run_repository or MemoryAnalysisRunRepository(),
        result_repository=result_repository or JsonResultRepository(),
    )
    return use_case, project


def build_text_report_generator() -> GenerateAnalysisReport:
    """Wire the plain-text ``GenerateAnalysisReport`` use case."""
    return GenerateAnalysisReport(TextAnalysisReportGenerator())


class PostgresUnavailableError(RuntimeError):
    """Raised when PostGIS-backed repositories are requested without the
    optional ``postgres`` extra (``psycopg``) installed."""


def build_postgres_repositories(
    dsn: str,
) -> tuple[
    "PostgresProjectRepository",
    "PostgresAnalysisRunRepository",
    "PostgresScreeningResultRepository",
]:
    """Wire process-shared, Postgres/PostGIS-backed repositories.

    Mirrors ``adapters.memory_repositories``'s three classes but persists to
    a database instead of an in-process dict — Step 2 of the plan in
    docs/WEB_ARCHITECTURE.md. Callers (``api/app.py``) pass these into
    ``build_file_screen_site`` exactly like the in-memory ones, so no route
    changes anywhere: only this composition wiring differs.

    The import of ``adapters.postgres`` (and, transitively, ``psycopg``) is
    deferred to inside this function rather than done at module level, so
    that importing ``composition`` — used by the CLI and Streamlit, which
    never call this function — never requires the optional ``postgres``
    extra to be installed.
    """
    try:
        from renewable_planner.adapters.postgres import (
            PostgresAnalysisRunRepository,
            PostgresProjectRepository,
            PostgresScreeningResultRepository,
        )
    except ImportError as error:
        raise PostgresUnavailableError(
            "PostGIS-backed repositories require the optional 'postgres' extra: "
            "pip install -e '.[postgres]'"
        ) from error

    projects = PostgresProjectRepository(dsn)
    runs = PostgresAnalysisRunRepository(dsn)
    results = PostgresScreeningResultRepository(dsn, runs)
    return projects, runs, results


def build_postgres_job_repository(dsn: str) -> "PostgresJobRepository":
    """Wire the Postgres-backed job queue (Step 3 of docs/WEB_ARCHITECTURE.md).

    Mirrors ``build_postgres_repositories``: the ``psycopg`` import is
    deferred so importing ``composition`` never requires the optional
    ``postgres`` extra unless this function is actually called.
    """
    try:
        from renewable_planner.adapters.postgres import PostgresJobRepository
    except ImportError as error:
        raise PostgresUnavailableError(
            "the job queue requires the optional 'postgres' extra: pip install -e '.[postgres]'"
        ) from error

    return PostgresJobRepository(dsn)
