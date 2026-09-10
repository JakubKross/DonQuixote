"""Command-line interface for DonQuixote."""

import argparse
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from renewable_planner import __version__
from renewable_planner.adapters.geospatial import (
    PyprojCoordinateReferenceSystemService,
    ShapelyAvailableAreaExtractor,
)
from renewable_planner.adapters.geospatial.file_screening import (
    FileScreeningError,
    load_site,
    write_screening_outputs,
    write_turbine_positions,
)
from renewable_planner.adapters.pywake_wind import PyWakeUnavailableError, PyWakeWindFarmSimulator
from renewable_planner.adapters.simple_wind_simulator import SimpleWindFarmSimulator
from renewable_planner.adapters.wind_catalog import (
    WindTurbineCatalogError,
    load_wind_turbine_catalog,
)
from renewable_planner.adapters.wind_resource import (
    WindResourceFileError,
    load_wind_resource_time_series,
)
from renewable_planner.application.spatial import ScreenSiteCommand, ScreenSiteError
from renewable_planner.application.wind import (
    GenerateTurbineLayout,
    GenerateTurbineLayoutCommand,
    GenerateTurbineLayoutError,
    NoAvailableAreaError,
)
from renewable_planner.composition import build_file_screen_site, build_text_report_generator
from renewable_planner.domain import (
    ScreenSiteResult,
    TurbinePosition,
    WindSimulationRequest,
    WindSimulationResult,
    WindTurbine,
    WindTurbineCatalog,
)
from renewable_planner.ports.wind import WindFarmSimulator


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
    screen_site.add_argument(
        "--turbine-catalog",
        type=Path,
        help="optional wind-turbine catalogue (YAML/JSON) to place turbines on the result",
    )
    screen_site.add_argument("--turbine-manufacturer")
    screen_site.add_argument("--turbine-model")
    screen_site.add_argument("--turbine-spacing-rotor-diameters", type=float)
    screen_site.add_argument("--turbine-grid-spacing-m", type=float)
    screen_site.add_argument(
        "--wind-resource",
        type=Path,
        help="optional hourly wind-resource series (YAML/JSON) to simulate energy production",
    )
    screen_site.add_argument(
        "--use-pywake",
        action="store_true",
        help="simulate wake losses with the optional PyWake adapter instead of the "
        "built-in no-wake simulator",
    )
    screen_site.add_argument("--technical-availability", type=float, default=1.0)
    screen_site.add_argument("--loss-factor", type=float, default=0.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "screen-site":
        try:
            _run_screen_site(arguments)
        except (
            FileScreeningError,
            OSError,
            ScreenSiteError,
            GenerateTurbineLayoutError,
            ValueError,
        ) as error:
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
    _validate_turbine_arguments(arguments)
    _validate_wind_simulation_arguments(arguments)

    site = load_site(arguments.site)
    use_case, project = build_file_screen_site(
        site, arguments.site, arguments.constraints, arguments.rules
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
    spatial = result.spatial_result
    warnings = sum(
        finding.level.value == "warning" and finding.status.value == "affected"
        for finding in spatial.findings
    )
    print(f"Powierzchnia początkowa: {spatial.initial_area_square_meters:.2f} m²")
    print(f"Powierzchnia wykluczona: {spatial.excluded_area_square_meters:.2f} m²")
    print(f"Powierzchnia dostępna: {spatial.available_area_square_meters:.2f} m²")
    print(f"Ostrzeżenia: {warnings}")

    wind_simulation_result: WindSimulationResult | None = None
    if arguments.turbine_catalog is not None:
        catalog = _load_turbine_catalog(arguments.turbine_catalog)
        turbine = _select_turbine(catalog, arguments.turbine_manufacturer, arguments.turbine_model)
        positions = _place_turbines(arguments, result, site.boundary.crs, turbine)
        if positions and arguments.wind_resource is not None:
            wind_simulation_result = _simulate_wind_production(arguments, turbine, positions)

    report = build_text_report_generator().execute(project, result)
    (arguments.output / "report.txt").write_text(report, encoding="utf-8")


def _validate_turbine_arguments(arguments: argparse.Namespace) -> None:
    turbine_options = (
        arguments.turbine_manufacturer,
        arguments.turbine_model,
        arguments.turbine_spacing_rotor_diameters,
        arguments.turbine_grid_spacing_m,
    )
    if arguments.turbine_catalog is None:
        if any(option is not None for option in turbine_options):
            raise FileScreeningError("turbine options require --turbine-catalog")
        return
    if not arguments.turbine_catalog.is_file():
        raise FileScreeningError(
            f"turbine-catalog file does not exist: {arguments.turbine_catalog}"
        )
    if arguments.turbine_spacing_rotor_diameters is None:
        raise FileScreeningError(
            "--turbine-spacing-rotor-diameters is required with --turbine-catalog"
        )
    if bool(arguments.turbine_manufacturer) != bool(arguments.turbine_model):
        raise FileScreeningError("--turbine-manufacturer and --turbine-model must be used together")

def _validate_wind_simulation_arguments(arguments: argparse.Namespace) -> None:
    if arguments.wind_resource is None:
        if arguments.use_pywake:
            raise FileScreeningError("--use-pywake requires --wind-resource")
        return
    if arguments.turbine_catalog is None:
        raise FileScreeningError("--wind-resource requires --turbine-catalog")
    if not arguments.wind_resource.is_file():
        raise FileScreeningError(f"wind-resource file does not exist: {arguments.wind_resource}")

def _load_turbine_catalog(path: Path) -> WindTurbineCatalog:
    try:
        return load_wind_turbine_catalog(path)
    except WindTurbineCatalogError as error:
        raise FileScreeningError(str(error)) from error

def _place_turbines(
    arguments: argparse.Namespace,
    result: ScreenSiteResult,
    crs: str,
    turbine: WindTurbine,
) -> tuple[TurbinePosition, ...] | None:
    """Generate deterministic turbine candidates for a completed screening run."""
    use_case = GenerateTurbineLayout(
        ShapelyAvailableAreaExtractor(PyprojCoordinateReferenceSystemService())
    )
    command = GenerateTurbineLayoutCommand(
        screening_result=result,
        turbine=turbine,
        spacing_rotor_diameters=arguments.turbine_spacing_rotor_diameters,
        grid_spacing_m=arguments.turbine_grid_spacing_m,
    )
    try:
        positions = use_case.execute(command)
    except NoAvailableAreaError:
        print("Brak dostępnego obszaru do rozmieszczenia turbin.")
        return None
    write_turbine_positions(positions, crs, arguments.output)
    print(f"Liczba wygenerowanych pozycji turbin: {len(positions)}")
    return positions

def _select_turbine(
    catalog: WindTurbineCatalog,
    manufacturer: str | None,
    model_name: str | None,
) -> WindTurbine:
    if manufacturer and model_name:
        turbine = catalog.find(manufacturer, model_name)
        if turbine is None:
            raise FileScreeningError(f"turbine not found in catalog: {manufacturer} {model_name}")
        return turbine
    if len(catalog.turbines) != 1:
        raise FileScreeningError(
            "--turbine-manufacturer and --turbine-model are required when the "
            "catalog contains more than one turbine"
        )
    return catalog.turbines[0]

def _simulate_wind_production(
    arguments: argparse.Namespace,
    turbine: WindTurbine,
    positions: Sequence[TurbinePosition],
) -> WindSimulationResult:
    """Simulate hourly energy production for the generated turbine layout.

    Uses the built-in, dependency-free simulator by default; ``--use-pywake``
    switches to the optional PyWake adapter for wake modeling.
    """
    try:
        series = load_wind_resource_time_series(arguments.wind_resource)
    except WindResourceFileError as error:
        raise FileScreeningError(str(error)) from error

    request = WindSimulationRequest(
        turbine=turbine,
        positions=tuple(positions),
        timestamps=series.timestamps,
        wind_speeds_mps=series.wind_speeds_mps,
        wind_directions_deg=series.wind_directions_deg,
        technical_availability=arguments.technical_availability,
        loss_factor=arguments.loss_factor,
    )
    simulator: WindFarmSimulator = (
        PyWakeWindFarmSimulator() if arguments.use_pywake else SimpleWindFarmSimulator()
    )
    try:
        result = simulator.simulate(request)
    except PyWakeUnavailableError as error:
        raise FileScreeningError(str(error)) from error

    print(f"AEP bez uwzględnienia wake: {result.no_wake_profile.total_energy_mwh:.2f} MWh")
    print(f"AEP z uwzględnieniem wake: {result.wake_profile.total_energy_mwh:.2f} MWh")
    print(f"Straty wake: {result.wake_loss_mwh:.2f} MWh ({result.wake_loss_fraction * 100:.2f}%)")
    return result
