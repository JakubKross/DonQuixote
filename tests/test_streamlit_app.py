"""Tests for the Streamlit prototype's non-rendering logic.

Deliberately does not import ``streamlit`` (an optional dependency) — every
function tested here is plain Python, per the module's own design.
"""

from datetime import date
from pathlib import Path

import pytest

from renewable_planner.streamlit_app import (
    CONFIG_DIR,
    ScreeningRequestError,
    _polygon_rings,
    area_summary,
    findings_table,
    list_sample_rule_files,
    render_schematic_map_svg,
    run_screening,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_list_sample_rule_files_finds_the_bundled_config() -> None:
    files = list_sample_rule_files()

    assert CONFIG_DIR.name == "config"
    assert any(path.name == "sample_rules.yaml" for path in files)
    assert files == tuple(sorted(files))


def test_run_screening_returns_a_full_outcome(tmp_path: Path) -> None:
    outcome = run_screening(
        site_path=FIXTURES / "cli_site.geojson",
        constraints_path=FIXTURES / "cli_constraints.geojson",
        rules_path=FIXTURES / "cli_rules.yaml",
        technology="wind",
        output_directory=tmp_path / "output",
        analysis_date=date(2026, 8, 17),
    )

    assert outcome.result.spatial_result.initial_area_square_meters == 400.0
    assert "RAPORT WSTĘPNEGO SCREENINGU TERENU" in outcome.report_text
    assert outcome.available_area_geojson["type"] == "FeatureCollection"
    assert outcome.metadata_json["analysis_run"]["status"] == "completed"


def test_run_screening_rejects_empty_technology(tmp_path: Path) -> None:
    with pytest.raises(ScreeningRequestError, match="technology"):
        run_screening(
            site_path=FIXTURES / "cli_site.geojson",
            constraints_path=FIXTURES / "cli_constraints.geojson",
            rules_path=FIXTURES / "cli_rules.yaml",
            technology="   ",
            output_directory=tmp_path / "output",
        )


def test_run_screening_wraps_adapter_errors(tmp_path: Path) -> None:
    with pytest.raises(ScreeningRequestError):
        run_screening(
            site_path=tmp_path / "missing.geojson",
            constraints_path=FIXTURES / "cli_constraints.geojson",
            rules_path=FIXTURES / "cli_rules.yaml",
            technology="wind",
            output_directory=tmp_path / "output",
        )


def test_area_summary_and_findings_table(tmp_path: Path) -> None:
    outcome = run_screening(
        site_path=FIXTURES / "cli_site.geojson",
        constraints_path=FIXTURES / "cli_constraints.geojson",
        rules_path=FIXTURES / "cli_rules.yaml",
        technology="wind",
        output_directory=tmp_path / "output",
        analysis_date=date(2026, 8, 17),
    )

    summary = area_summary(outcome)
    assert summary["Powierzchnia początkowa (m²)"] == 400.0

    rows = findings_table(outcome)
    assert rows
    assert {"reguła", "poziom", "status", "źródło", "wersja", "komunikat"} <= rows[0].keys()


def test_polygon_rings_extracts_polygon_and_multipolygon() -> None:
    polygon = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    multipolygon = {
        "type": "MultiPolygon",
        "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]], [[[2, 2], [3, 2], [3, 3], [2, 2]]]],
    }

    assert _polygon_rings(polygon) == [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]]
    assert len(_polygon_rings(multipolygon)) == 2
    assert _polygon_rings({"type": "Point", "coordinates": [0, 0]}) == []


def test_render_schematic_map_svg_draws_layers() -> None:
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
                },
            }
        ],
    }

    svg = render_schematic_map_svg([(collection, "#2e9f43")])

    assert svg.startswith("<svg")
    assert "#2e9f43" in svg
    assert "path" in svg


def test_render_schematic_map_svg_returns_empty_string_for_no_geometry() -> None:
    empty_collection = {"type": "FeatureCollection", "features": []}

    assert render_schematic_map_svg([(empty_collection, "#2e9f43")]) == ""
