import json
from pathlib import Path

import pytest

from renewable_planner import __version__
from renewable_planner.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_displays_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"DonQuixote {__version__}"


def test_cli_screen_site_writes_summary_and_spatial_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"

    assert (
        main(
            [
                "screen-site",
                "--site",
                str(FIXTURES / "cli_site.geojson"),
                "--constraints",
                str(FIXTURES / "cli_constraints.geojson"),
                "--rules",
                str(FIXTURES / "cli_rules.yaml"),
                "--technology",
                "wind",
                "--analysis-date",
                "2026-08-17",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    summary = capsys.readouterr().out
    assert "Powierzchnia początkowa: 400.00 m²" in summary
    assert "Powierzchnia wykluczona:" in summary
    assert "Powierzchnia dostępna:" in summary
    assert "Ostrzeżenia: 1" in summary

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["analysis_run"]["status"] == "completed"
    assert metadata["warnings"] == 1
    assert metadata["data_versions"]["layer:buildings"] == "v1"
    assert metadata["data_versions"]["rule:20000000-0000-0000-0000-000000000001"] == "rules-v1"
    assert json.loads((output / "available_area.geojson").read_text(encoding="utf-8"))["type"] == (
        "FeatureCollection"
    )
    assert json.loads((output / "excluded_areas.geojson").read_text(encoding="utf-8"))["features"]


def test_cli_rejects_missing_input_file(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(
            [
                "screen-site",
                "--site",
                "missing.geojson",
                "--constraints",
                "missing-constraints.geojson",
                "--rules",
                "missing-rules.yaml",
                "--technology",
                "wind",
                "--output",
                "outputs",
            ]
        )

    assert exit_info.value.code == 2
    assert "site file does not exist" in capsys.readouterr().err
