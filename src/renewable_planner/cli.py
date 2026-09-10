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
from renewable_planner.adapters.pvlib_solar import PvlibSolarArraySimulator, PvlibUnavailableError
from renewable_planner.adapters.pywake_wind import PyWakeUnavailableError, PyWakeWindFarmSimulator
from renewable_planner.adapters.simple_solar_simulator import SimpleSolarArraySimulator
from renewable_planner.adapters.simple_wind_simulator import SimpleWindFarmSimulator
from renewable_planner.adapters.solar_catalog import (
    SolarModuleCatalogError,
    load_solar_module_catalog,
)
from renewable_planner.adapters.solar_resource import (
    SolarResourceFileError,
    load_solar_resource_time_series,
)
from renewable_planner.adapters.wind_catalog import (
    WindTurbineCatalogError,
    load_wind_turbine_catalog,
)
from renewable_planner.adapters.wind_resource import (
    WindResourceFileError,
    load_wind_resource_time_series,
)
from renewable_planner.application.hybrid import (
    AggregateHybridProduction,
    AggregateHybridProductionCommand,
)
from renewable_planner.application.solar import (
    NoAvailableAreaError as NoAvailableSolarAreaError,
)
from renewable_planner.application.solar import (
    SizeSolarArray,
    SizeSolarArrayCommand,
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
    EnergyProfile,
    GridConnectionLimit,
    GroundCoverageRatio,
    HybridProductionResult,
    ScreenSiteResult,
    SolarModule,
    SolarModuleCatalog,
    SolarSimulationRequest,
    SolarSimulationResult,
    TurbinePosition,
    WindSimulationRequest,
    WindSimulationResult,
    WindTurbine,
    WindTurbineCatalog,
)
from renewable_planner.ports.solar import SolarArraySimulator
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
    screen_site.add_argument(
        "--solar-catalog",
        type=Path,
        help="optional PV-module catalogue (YAML/JSON) to size an array on the result",
    )
    screen_site.add_argument("--solar-manufacturer")
    screen_site.add_argument("--solar-model")
    screen_site.add_argument("--solar-ground-coverage-ratio", type=float)
    screen_site.add_argument(
        "--solar-resource",
        type=Path,
        help="optional hourly solar-resource series (YAML/JSON) to simulate energy production",
    )
    screen_site.add_argument(
        "--use-pvlib",
        action="store_true",
        help="convert DC to AC with the optional pvlib PVWatts inverter model instead of "
        "the built-in lossless-inverter simulator",
    )
    screen_site.add_argument("--solar-technical-availability", type=float, default=1.0)
    screen_site.add_argument("--solar-loss-factor", type=float, default=0.0)
    screen_site.add_argument(
        "--grid-connection-limit-mw",
        type=float,
        help="optional grid connection export limit (MW); combines and curtails "
        "whichever wind/solar production simulations were run",
    )
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
    _validate_solar_arguments(arguments)
    _validate_solar_simulation_arguments(arguments)
    _validate_hybrid_arguments(arguments)

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

    solar_simulation_result: SolarSimulationResult | None = None
    if arguments.solar_catalog is not None:
        solar_catalog = _load_solar_catalog(arguments.solar_catalog)
        module = _select_solar_module(
            solar_catalog, arguments.solar_manufacturer, arguments.solar_model
        )
        module_count = _size_solar_array(arguments, result, module)
        if module_count > 0 and arguments.solar_resource is not None:
            solar_simulation_result = _simulate_solar_production(arguments, module, module_count)

    hybrid_result: HybridProductionResult | None = None
    if arguments.grid_connection_limit_mw is not None:
        hybrid_result = _aggregate_hybrid_production(
            arguments, wind_simulation_result, solar_simulation_result
        )

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


def _validate_solar_arguments(arguments: argparse.Namespace) -> None:
    solar_options = (
        arguments.solar_manufacturer,
        arguments.solar_model,
        arguments.solar_ground_coverage_ratio,
    )
    if arguments.solar_catalog is None:
        if any(option is not None for option in solar_options):
            raise FileScreeningError("solar options require --solar-catalog")
        return
    if not arguments.solar_catalog.is_file():
        raise FileScreeningError(f"solar-catalog file does not exist: {arguments.solar_catalog}")
    if arguments.solar_ground_coverage_ratio is None:
        raise FileScreeningError("--solar-ground-coverage-ratio is required with --solar-catalog")
    if bool(arguments.solar_manufacturer) != bool(arguments.solar_model):
        raise FileScreeningError("--solar-manufacturer and --solar-model must be used together")

def _validate_solar_simulation_arguments(arguments: argparse.Namespace) -> None:
    if arguments.solar_resource is None:
        if arguments.use_pvlib:
            raise FileScreeningError("--use-pvlib requires --solar-resource")
        return
    if arguments.solar_catalog is None:
        raise FileScreeningError("--solar-resource requires --solar-catalog")
    if not arguments.solar_resource.is_file():
        raise FileScreeningError(f"solar-resource file does not exist: {arguments.solar_resource}")

def _load_solar_catalog(path: Path) -> SolarModuleCatalog:
    try:
        return load_solar_module_catalog(path)
    except SolarModuleCatalogError as error:
        raise FileScreeningError(str(error)) from error

def _select_solar_module(
    catalog: SolarModuleCatalog,
    manufacturer: str | None,
    model_name: str | None,
) -> SolarModule:
    if manufacturer and model_name:
        module = catalog.find(manufacturer, model_name)
        if module is None:
            raise FileScreeningError(
                f"solar module not found in catalog: {manufacturer} {model_name}"
            )
        return module
    if len(catalog.modules) != 1:
        raise FileScreeningError(
            "--solar-manufacturer and --solar-model are required when the "
            "catalog contains more than one module"
        )
    return catalog.modules[0]

def _size_solar_array(
    arguments: argparse.Namespace,
    result: ScreenSiteResult,
    module: SolarModule,
) -> int:
    """Size a PV array on the screening's available area and report it."""
    use_case = SizeSolarArray()
    command = SizeSolarArrayCommand(
        screening_result=result,
        module=module,
        ground_coverage_ratio=GroundCoverageRatio(arguments.solar_ground_coverage_ratio),
    )
    try:
        layout = use_case.execute(command)
    except NoAvailableSolarAreaError:
        print("Brak dostępnego obszaru do posadowienia instalacji PV.")
        return 0
    print(
        f"Liczba modułów PV: {layout.module_count} "
        f"(moc zainstalowana: {layout.installed_capacity_w / 1000:.2f} kWp)"
    )
    return layout.module_count

def _simulate_solar_production(
    arguments: argparse.Namespace,
    module: SolarModule,
    module_count: int,
) -> SolarSimulationResult:
    """Simulate hourly energy production for the sized PV array.

    Uses the built-in, dependency-free simulator by default; ``--use-pvlib``
    switches to the optional pvlib PVWatts inverter model.
    """
    try:
        series = load_solar_resource_time_series(arguments.solar_resource)
    except SolarResourceFileError as error:
        raise FileScreeningError(str(error)) from error

    request = SolarSimulationRequest(
        module=module,
        module_count=module_count,
        timestamps=series.timestamps,
        poa_irradiance_w_per_m2=series.poa_irradiance_w_per_m2,
        ambient_temperature_c=series.ambient_temperature_c,
        technical_availability=arguments.solar_technical_availability,
        loss_factor=arguments.solar_loss_factor,
    )
    simulator: SolarArraySimulator = (
        PvlibSolarArraySimulator() if arguments.use_pvlib else SimpleSolarArraySimulator()
    )
    try:
        result = simulator.simulate(request)
    except PvlibUnavailableError as error:
        raise FileScreeningError(str(error)) from error

    print(f"AEP DC (przed inwerterem): {result.dc_profile.total_energy_mwh:.2f} MWh")
    print(f"AEP AC (po inwerterze): {result.ac_profile.total_energy_mwh:.2f} MWh")
    print(
        f"Straty inwertera: {result.inverter_loss_mwh:.2f} MWh "
        f"({result.inverter_loss_fraction * 100:.2f}%)"
    )
    return result


def _validate_hybrid_arguments(arguments: argparse.Namespace) -> None:
    if arguments.grid_connection_limit_mw is None:
        return
    if arguments.grid_connection_limit_mw <= 0:
        raise FileScreeningError("--grid-connection-limit-mw must be greater than zero")
    if arguments.wind_resource is None and arguments.solar_resource is None:
        raise FileScreeningError(
            "--grid-connection-limit-mw requires --wind-resource and/or --solar-resource"
        )

def _aggregate_hybrid_production(
    arguments: argparse.Namespace,
    wind_simulation_result: WindSimulationResult | None,
    solar_simulation_result: SolarSimulationResult | None,
) -> HybridProductionResult | None:
    """Combine whichever wind/solar simulations actually ran and curtail the total.

    Returns ``None`` when neither simulation produced a profile (e.g. both
    left no available area), so the report can say so explicitly instead of
    showing a misleadingly empty aggregate.
    """
    profiles: list[EnergyProfile] = []
    if wind_simulation_result is not None:
        profiles.append(wind_simulation_result.wake_profile)
    if solar_simulation_result is not None:
        profiles.append(solar_simulation_result.ac_profile)
    if not profiles:
        print(
            "Brak profili produkcji do agregacji hybrydowej "
            "(żadna symulacja wiatru/PV nie została uruchomiona)."
        )
        return None

    use_case = AggregateHybridProduction()
    command = AggregateHybridProductionCommand(
        profiles=tuple(profiles),
        connection_limit=GridConnectionLimit(arguments.grid_connection_limit_mw),
    )
    result = use_case.execute(command)

    curtailment = result.curtailment
    print(
        "Produkcja łączna (przed ograniczeniem przyłącza): "
        f"{result.aggregate_profile.total_energy_mwh:.2f} MWh"
    )
    print(
        "Dostarczone do sieci (po ograniczeniu przyłącza): "
        f"{curtailment.delivered_profile.total_energy_mwh:.2f} MWh"
    )
    print(
        f"Curtailment: {curtailment.curtailed_energy_mwh:.2f} MWh "
        f"({curtailment.curtailed_energy_fraction * 100:.2f}%)"
    )
    print(f"Wykorzystanie przyłącza: {curtailment.utilization_fraction * 100:.2f}%")
    return result
