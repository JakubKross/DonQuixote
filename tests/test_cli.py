import json
from pathlib import Path

import pytest
import yaml

from renewable_planner import __version__
from renewable_planner.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _screen_site_args(output: Path, **extra: str) -> list[str]:
    arguments = [
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
    for name, value in extra.items():
        arguments.extend([f"--{name.replace('_', '-')}", value])
    return arguments


def test_cli_displays_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"DonQuixote {__version__}"


def test_cli_screen_site_writes_summary_and_spatial_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"

    assert main(_screen_site_args(output)) == 0

    summary = capsys.readouterr().out
    assert "Powierzchnia początkowa: 400.00 m²" in summary
    assert "Powierzchnia wykluczona:" in summary
    assert "Powierzchnia dostępna:" in summary
    assert "Ostrzeżenia: 1" in summary

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["analysis_run"]["status"] == "completed"
    assert metadata["warnings"] == 1
    assert metadata["data_versions"]["layer:buildings"] == "v1"
    assert (
        metadata["data_versions"]["rule:20000000-0000-0000-0000-000000000001"]
        == "yaml:20000000-0000-0000-0000-000000000001"
    )
    assert json.loads((output / "available_area.geojson").read_text(encoding="utf-8"))["type"] == (
        "FeatureCollection"
    )
    assert json.loads((output / "excluded_areas.geojson").read_text(encoding="utf-8"))["features"]

    report = (output / "report.txt").read_text(encoding="utf-8")
    for section in (
        "Nazwa projektu:",
        "Identyfikator analizy:",
        "Data uruchomienia:",
        "Technologia:",
        "ŹRÓDŁA I WERSJE DANYCH",
        "ZASTOSOWANE REGUŁY",
        "WYKRYTE WYKLUCZENIA",
        "OSTRZEŻENIA",
        "PODSUMOWANIE POWIERZCHNI",
        "Powierzchnia początkowa:",
        "Powierzchnia wykluczona:",
        "Powierzchnia dostępna:",
        "PRODUKCJA ENERGII (WIATR)",
        "PRODUKCJA ENERGII (PV)",
        "AGREGACJA HYBRYDOWA I PRZYŁĄCZE",
        "MAGAZYN ENERGII (BATERIA)",
        "OGRANICZENIA WYNIKU",
        "nie jest wiążącą opinią prawną",
        "nie gwarantuje możliwości realizacji inwestycji",
    ):
        assert section in report


def test_cli_screen_site_places_turbines_when_catalog_is_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"

    exit_code = main(
        _screen_site_args(
            output,
            turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
            turbine_spacing_rotor_diameters="1",
        )
    )

    assert exit_code == 0
    summary = capsys.readouterr().out
    assert "Liczba wygenerowanych pozycji turbin:" in summary

    positions = json.loads((output / "turbine_positions.geojson").read_text(encoding="utf-8"))
    assert positions["type"] == "FeatureCollection"
    assert positions["crs"]["properties"]["name"] == "EPSG:2180"
    assert positions["features"]
    assert all(feature["geometry"]["type"] == "Point" for feature in positions["features"])


def test_cli_reports_when_no_area_remains_for_turbines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"
    site = tmp_path / "site.geojson"
    site.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:2180"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[2, 2], [5, 2], [5, 5], [2, 5], [2, 2]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "screen-site",
            "--site",
            str(site),
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
            "--turbine-catalog",
            str(FIXTURES / "cli_turbine_catalog.yaml"),
            "--turbine-spacing-rotor-diameters",
            "1",
        ]
    )

    assert exit_code == 0
    assert "Brak dostępnego obszaru do rozmieszczenia turbin." in capsys.readouterr().out
    assert not (output / "turbine_positions.geojson").exists()


def test_cli_rejects_turbine_options_without_catalog(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_spacing_rotor_diameters="1",
            )
        )

    assert exit_info.value.code == 2


def test_cli_rejects_catalog_without_spacing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
            )
        )

    assert "--turbine-spacing-rotor-diameters is required" in capsys.readouterr().err


def test_cli_rejects_manufacturer_without_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
                turbine_spacing_rotor_diameters="1",
                turbine_manufacturer="Fikcyjny Wind",
            )
        )

    assert "must be used together" in capsys.readouterr().err


def test_cli_rejects_ambiguous_catalog_without_selection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog = tmp_path / "catalog.yaml"
    turbine = {
        "manufacturer": "Fikcyjny Wind",
        "model_name": "FW-Test",
        "rated_power_kw": 100,
        "rotor_diameter_m": 2,
        "hub_height_m": 10,
        "cut_in_wind_speed_mps": 3,
        "rated_wind_speed_mps": 10,
        "cut_out_wind_speed_mps": 25,
        "power_curve": [
            {"wind_speed_mps": 3, "power_kw": 0},
            {"wind_speed_mps": 10, "power_kw": 100},
        ],
        "data_source": "synthetic-test-dataset",
        "data_version": "test-v1",
    }
    other = dict(turbine, model_name="FW-Test-2")
    catalog.write_text(yaml.safe_dump({"turbines": [turbine, other]}), encoding="utf-8")

    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(catalog),
                turbine_spacing_rotor_diameters="1",
            )
        )

    assert "more than one turbine" in capsys.readouterr().err


def test_cli_rejects_unknown_turbine_selection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
                turbine_spacing_rotor_diameters="1",
                turbine_manufacturer="Nieznany",
                turbine_model="Nieznany",
            )
        )

    assert "turbine not found in catalog" in capsys.readouterr().err


def test_cli_simulates_wind_production_with_the_default_no_wake_simulator(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"

    exit_code = main(
        _screen_site_args(
            output,
            turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
            turbine_spacing_rotor_diameters="1",
            wind_resource=str(FIXTURES / "wind_resource_sample.yaml"),
        )
    )

    assert exit_code == 0
    summary = capsys.readouterr().out
    assert "AEP bez uwzględnienia wake:" in summary
    assert "AEP z uwzględnieniem wake:" in summary
    assert "Straty wake: 0.00 MWh (0.00%)" in summary

    report = (output / "report.txt").read_text(encoding="utf-8")
    assert "AEP bez uwzględnienia wake:" in report
    assert "Symulacji produkcji energii wiatrowej nie uruchomiono" not in report
    assert "Symulacji produkcji energii PV nie uruchomiono" in report


def test_cli_rejects_wind_resource_without_turbine_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                wind_resource=str(FIXTURES / "wind_resource_sample.yaml"),
            )
        )

    assert "--wind-resource requires --turbine-catalog" in capsys.readouterr().err


def test_cli_rejects_use_pywake_without_wind_resource(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _screen_site_args(
        tmp_path / "screening",
        turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
        turbine_spacing_rotor_diameters="1",
    )
    arguments.append("--use-pywake")

    with pytest.raises(SystemExit):
        main(arguments)

    assert "--use-pywake requires --wind-resource" in capsys.readouterr().err


def test_cli_rejects_missing_wind_resource_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
                turbine_spacing_rotor_diameters="1",
                wind_resource=str(tmp_path / "missing-wind.yaml"),
            )
        )

    assert "wind-resource file does not exist" in capsys.readouterr().err


def test_cli_sizes_solar_array_when_catalog_is_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"

    exit_code = main(
        _screen_site_args(
            output,
            solar_catalog=str(FIXTURES / "cli_solar_catalog.yaml"),
            solar_ground_coverage_ratio="0.4",
        )
    )

    assert exit_code == 0
    assert "Liczba modułów PV:" in capsys.readouterr().out


def test_cli_reports_when_no_area_remains_for_solar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"
    site = tmp_path / "site.geojson"
    site.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:2180"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[2, 2], [5, 2], [5, 5], [2, 5], [2, 2]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "screen-site",
            "--site",
            str(site),
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
            "--solar-catalog",
            str(FIXTURES / "cli_solar_catalog.yaml"),
            "--solar-ground-coverage-ratio",
            "0.4",
        ]
    )

    assert exit_code == 0
    assert "Brak dostępnego obszaru do posadowienia instalacji PV." in capsys.readouterr().out


def test_cli_simulates_solar_production_with_the_default_lossless_simulator(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"

    exit_code = main(
        _screen_site_args(
            output,
            solar_catalog=str(FIXTURES / "cli_solar_catalog.yaml"),
            solar_ground_coverage_ratio="0.4",
            solar_resource=str(FIXTURES / "solar_resource_sample.yaml"),
        )
    )

    assert exit_code == 0
    summary = capsys.readouterr().out
    assert "AEP DC (przed inwerterem):" in summary
    assert "AEP AC (po inwerterze):" in summary
    assert "Straty inwertera: 0.00 MWh (0.00%)" in summary

    report = (output / "report.txt").read_text(encoding="utf-8")
    assert "AEP DC (przed inwerterem):" in report
    assert "Symulacji produkcji energii PV nie uruchomiono" not in report


def test_cli_rejects_solar_options_without_catalog(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(
            _screen_site_args(
                tmp_path / "screening",
                solar_ground_coverage_ratio="0.4",
            )
        )

    assert exit_info.value.code == 2


def test_cli_rejects_catalog_without_ground_coverage_ratio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                solar_catalog=str(FIXTURES / "cli_solar_catalog.yaml"),
            )
        )

    assert "--solar-ground-coverage-ratio is required" in capsys.readouterr().err


def test_cli_rejects_solar_manufacturer_without_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                solar_catalog=str(FIXTURES / "cli_solar_catalog.yaml"),
                solar_ground_coverage_ratio="0.4",
                solar_manufacturer="Fikcyjny Solar",
            )
        )

    assert "must be used together" in capsys.readouterr().err


def test_cli_rejects_unknown_solar_module_selection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                solar_catalog=str(FIXTURES / "cli_solar_catalog.yaml"),
                solar_ground_coverage_ratio="0.4",
                solar_manufacturer="Nieznany",
                solar_model="Nieznany",
            )
        )

    assert "solar module not found in catalog" in capsys.readouterr().err


def test_cli_rejects_solar_resource_without_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                solar_resource=str(FIXTURES / "solar_resource_sample.yaml"),
            )
        )

    assert "--solar-resource requires --solar-catalog" in capsys.readouterr().err


def test_cli_rejects_use_pvlib_without_solar_resource(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _screen_site_args(
        tmp_path / "screening",
        solar_catalog=str(FIXTURES / "cli_solar_catalog.yaml"),
        solar_ground_coverage_ratio="0.4",
    )
    arguments.append("--use-pvlib")

    with pytest.raises(SystemExit):
        main(arguments)

    assert "--use-pvlib requires --solar-resource" in capsys.readouterr().err


def test_cli_rejects_missing_solar_resource_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                solar_catalog=str(FIXTURES / "cli_solar_catalog.yaml"),
                solar_ground_coverage_ratio="0.4",
                solar_resource=str(tmp_path / "missing-solar.yaml"),
            )
        )

    assert "solar-resource file does not exist" in capsys.readouterr().err


def test_cli_aggregates_and_curtails_wind_production_with_a_grid_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"

    exit_code = main(
        _screen_site_args(
            output,
            turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
            turbine_spacing_rotor_diameters="1",
            wind_resource=str(FIXTURES / "wind_resource_sample.yaml"),
            grid_connection_limit_mw="0.0001",
        )
    )

    assert exit_code == 0
    summary = capsys.readouterr().out
    assert "Produkcja łączna (przed ograniczeniem przyłącza):" in summary
    assert "Dostarczone do sieci (po ograniczeniu przyłącza):" in summary
    assert "Wykorzystanie przyłącza:" in summary

    report = (output / "report.txt").read_text(encoding="utf-8")
    assert "AGREGACJA HYBRYDOWA I PRZYŁĄCZE" in report
    assert "Agregacji hybrydowej i limitu przyłącza nie uruchomiono" not in report


def test_cli_reports_when_no_simulation_ran_for_hybrid_aggregation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"
    site = tmp_path / "site.geojson"
    site.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:2180"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[2, 2], [5, 2], [5, 5], [2, 5], [2, 2]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "screen-site",
            "--site",
            str(site),
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
            "--turbine-catalog",
            str(FIXTURES / "cli_turbine_catalog.yaml"),
            "--turbine-spacing-rotor-diameters",
            "1",
            "--wind-resource",
            str(FIXTURES / "wind_resource_sample.yaml"),
            "--grid-connection-limit-mw",
            "1",
        ]
    )

    assert exit_code == 0
    assert "Brak profili produkcji do agregacji hybrydowej" in capsys.readouterr().out


def test_cli_rejects_mismatched_wind_and_solar_resource_timestamps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
                turbine_spacing_rotor_diameters="1",
                wind_resource=str(FIXTURES / "wind_resource_sample.yaml"),
                solar_catalog=str(FIXTURES / "cli_solar_catalog.yaml"),
                solar_ground_coverage_ratio="0.4",
                solar_resource=str(FIXTURES / "solar_resource_sample.yaml"),
                grid_connection_limit_mw="1",
            )
        )

    assert "same timestamps" in capsys.readouterr().err


def test_cli_rejects_non_positive_grid_connection_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
                turbine_spacing_rotor_diameters="1",
                wind_resource=str(FIXTURES / "wind_resource_sample.yaml"),
                grid_connection_limit_mw="0",
            )
        )

    assert "--grid-connection-limit-mw must be greater than zero" in capsys.readouterr().err


def test_cli_rejects_grid_connection_limit_without_any_resource(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                grid_connection_limit_mw="1",
            )
        )

    assert (
        "--grid-connection-limit-mw requires --wind-resource and/or --solar-resource"
        in capsys.readouterr().err
    )


def test_cli_dispatches_battery_and_reduces_curtailment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "screening"

    exit_code = main(
        _screen_site_args(
            output,
            turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
            turbine_spacing_rotor_diameters="1",
            wind_resource=str(FIXTURES / "wind_resource_sample.yaml"),
            grid_connection_limit_mw="0.0001",
            battery_catalog=str(FIXTURES / "cli_battery_catalog.yaml"),
        )
    )

    assert exit_code == 0
    summary = capsys.readouterr().out
    assert "Naładowano:" in summary
    assert "Curtailment po wsparciu magazynu:" in summary

    report = (output / "report.txt").read_text(encoding="utf-8")
    assert "MAGAZYN ENERGII (BATERIA)" in report
    assert "Symulacji magazynu energii nie uruchomiono" not in report

    # The battery should absorb at least some of the surplus that plain
    # curtailment (without a battery) would have thrown away.
    plain_curtailment = float(
        next(
            line.split(":")[1].split("MWh")[0].strip()
            for line in report.splitlines()
            if line.startswith("Curtailment:")
        )
    )
    battery_curtailment = float(
        next(
            line.split(":")[1].split("MWh")[0].strip()
            for line in report.splitlines()
            if line.startswith("Curtailment po wsparciu magazynu:")
        )
    )
    assert battery_curtailment < plain_curtailment


def test_cli_rejects_battery_options_without_catalog(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(
            _screen_site_args(
                tmp_path / "screening",
                battery_initial_soc="0.5",
            )
        )

    assert exit_info.value.code == 2


def test_cli_rejects_battery_catalog_without_grid_connection_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
                turbine_spacing_rotor_diameters="1",
                wind_resource=str(FIXTURES / "wind_resource_sample.yaml"),
                battery_catalog=str(FIXTURES / "cli_battery_catalog.yaml"),
            )
        )

    assert "--battery-catalog requires --grid-connection-limit-mw" in capsys.readouterr().err


def test_cli_rejects_battery_manufacturer_without_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
                turbine_spacing_rotor_diameters="1",
                wind_resource=str(FIXTURES / "wind_resource_sample.yaml"),
                grid_connection_limit_mw="0.0001",
                battery_catalog=str(FIXTURES / "cli_battery_catalog.yaml"),
                battery_manufacturer="Fikcyjny Storage",
            )
        )

    assert "must be used together" in capsys.readouterr().err


def test_cli_rejects_unknown_battery_selection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(
            _screen_site_args(
                tmp_path / "screening",
                turbine_catalog=str(FIXTURES / "cli_turbine_catalog.yaml"),
                turbine_spacing_rotor_diameters="1",
                wind_resource=str(FIXTURES / "wind_resource_sample.yaml"),
                grid_connection_limit_mw="0.0001",
                battery_catalog=str(FIXTURES / "cli_battery_catalog.yaml"),
                battery_manufacturer="Nieznany",
                battery_model="Nieznany",
            )
        )

    assert "battery not found in catalog" in capsys.readouterr().err


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
