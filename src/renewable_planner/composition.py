"""Shared composition helpers for file-driven interfaces (CLI, Streamlit, API).

Every interface that reads a site boundary, constraint layers and rules from
files needs the exact same wiring of adapters into the ``ScreenSite`` use
case. Defining that wiring once here means no interface has to duplicate
screening logic or composition — each one only supplies file paths.
"""

from pathlib import Path

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


def build_file_screen_site(
    site: Site,
    site_path: Path,
    constraints_path: Path,
    rules_path: Path,
    *,
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
    """
    project = build_project(site, site_path)
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
