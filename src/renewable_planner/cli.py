"""Command-line interface for DonQuixote."""

import argparse
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from renewable_planner import __version__
from renewable_planner.adapters.geospatial import (
    GeoPandasSpatialOperations,
    PyprojCoordinateReferenceSystemService,
)
from renewable_planner.adapters.geospatial.file_screening import (
    FileProjectRepository,
    FileScreeningError,
    FileSiteRepository,
    GeoJsonConstraintLayerProvider,
    JsonResultRepository,
    MemoryAnalysisRunRepository,
    YamlSpatialRuleProvider,
    build_project,
    load_site,
    write_screening_outputs,
)
from renewable_planner.adapters.reporting import TextAnalysisReportGenerator
from renewable_planner.application.reporting import GenerateAnalysisReport
from renewable_planner.application.spatial import (
    ScreenSite,
    ScreenSiteCommand,
    ScreenSiteError,
    SpatialRuleEngine,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(prog="DonQuixote")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    commands = parser.add_subparsers(dest="command")
    screen_site = commands.add_parser("screen-site", help="run spatial site screening")
    screen_site.add_argument("--site", type=Path, required=True)
    screen_site.add_argument("--constraints", type=Path, required=True)
    screen_site.add_argument("--rules", type=Path, required=True)
    screen_site.add_argument("--technology", required=True)
    screen_site.add_argument("--output", type=Path, required=True)
    screen_site.add_argument("--country", default="PL")
    screen_site.add_argument("--analysis-date", type=_parse_date, default=date.today())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "screen-site":
        try:
            _run_screen_site(arguments)
        except (FileScreeningError, OSError, ScreenSiteError, ValueError) as error:
            parser.error(str(error))
    return 0


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("analysis date must use YYYY-MM-DD") from error


def _run_screen_site(arguments: argparse.Namespace) -> None:
    for name in ("site", "constraints", "rules"):
        path = getattr(arguments, name)
        if not path.is_file():
            raise FileScreeningError(f"{name} file does not exist: {path}")
    if not arguments.technology.strip():
        raise FileScreeningError("technology must not be empty")

    site = load_site(arguments.site)
    project = build_project(site, arguments.site)
    runs = MemoryAnalysisRunRepository()
    results = JsonResultRepository()
    use_case = ScreenSite(
        project_repository=FileProjectRepository(project),
        site_repository=FileSiteRepository(site),
        rule_provider=YamlSpatialRuleProvider(arguments.rules),
        layer_provider=GeoJsonConstraintLayerProvider(arguments.constraints, site.boundary.crs),
        rule_evaluator=SpatialRuleEngine(
            GeoPandasSpatialOperations(PyprojCoordinateReferenceSystemService())
        ),
        analysis_run_repository=runs,
        result_repository=results,
    )
    result = use_case.execute(
        ScreenSiteCommand(
            project_id=project.id,
            site_id=site.id,
            country=arguments.country,
            technology=arguments.technology,
            analysis_date=arguments.analysis_date,
        )
    )
    write_screening_outputs(result, arguments.output)
    report = GenerateAnalysisReport(TextAnalysisReportGenerator()).execute(project, result)
    (arguments.output / "report.txt").write_text(report, encoding="utf-8")
    spatial = result.spatial_result
    warnings = sum(
        finding.level.value == "warning" and finding.status.value == "affected"
        for finding in spatial.findings
    )
    print(f"Powierzchnia początkowa: {spatial.initial_area_square_meters:.2f} m²")
    print(f"Powierzchnia wykluczona: {spatial.excluded_area_square_meters:.2f} m²")
    print(f"Powierzchnia dostępna: {spatial.available_area_square_meters:.2f} m²")
    print(f"Ostrzeżenia: {warnings}")
