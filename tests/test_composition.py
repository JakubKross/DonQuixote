from datetime import date
from pathlib import Path

from renewable_planner.adapters.geospatial.file_screening import load_site
from renewable_planner.application.spatial import ScreenSiteCommand
from renewable_planner.composition import build_file_screen_site, build_text_report_generator
from renewable_planner.domain import AnalysisRunStatus, ScreenSiteResult

FIXTURES = Path(__file__).parent / "fixtures"
ANALYSIS_DATE = date(2026, 8, 17)


def test_build_file_screen_site_wires_a_working_use_case() -> None:
    site_path = FIXTURES / "cli_site.geojson"
    site = load_site(site_path)

    use_case, project = build_file_screen_site(
        site,
        site_path,
        FIXTURES / "cli_constraints.geojson",
        FIXTURES / "cli_rules.yaml",
    )
    result = use_case.execute(
        ScreenSiteCommand(
            project_id=project.id,
            site_id=site.id,
            country="PL",
            technology="wind",
            analysis_date=ANALYSIS_DATE,
        )
    )

    assert isinstance(result, ScreenSiteResult)
    assert result.analysis_run.status is AnalysisRunStatus.COMPLETED
    assert result.spatial_result.initial_area_square_meters == 400.0


def test_build_text_report_generator_renders_a_report() -> None:
    site_path = FIXTURES / "cli_site.geojson"
    site = load_site(site_path)
    use_case, project = build_file_screen_site(
        site,
        site_path,
        FIXTURES / "cli_constraints.geojson",
        FIXTURES / "cli_rules.yaml",
    )
    result = use_case.execute(
        ScreenSiteCommand(
            project_id=project.id,
            site_id=site.id,
            country="PL",
            technology="wind",
            analysis_date=ANALYSIS_DATE,
        )
    )

    report = build_text_report_generator().execute(project, result)

    assert "RAPORT WSTĘPNEGO SCREENINGU TERENU" in report
