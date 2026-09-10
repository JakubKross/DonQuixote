from datetime import UTC, datetime, timedelta

from renewable_planner.application.reporting import GenerateAnalysisReport
from renewable_planner.domain import (
    AnalysisRun,
    AnalysisRunStatus,
    Battery,
    BatteryDispatcher,
    BatteryDispatchResult,
    CurtailmentResult,
    EnergyProfile,
    EnergySample,
    HybridProductionResult,
    Project,
    ScreenSiteResult,
    SolarSimulationResult,
    SpatialRuleEngineResult,
    WindSimulationResult,
)
from renewable_planner.ports.reporting import AnalysisReportRequest

START = datetime(2026, 1, 1, tzinfo=UTC)


class StubReportGenerator:
    """Test double recording the request it was asked to render."""

    def __init__(self) -> None:
        self.received: AnalysisReportRequest | None = None

    def generate(self, request: AnalysisReportRequest) -> str:
        self.received = request
        return "rendered"


def _project() -> Project:
    return Project(name="Testowa farma")


def _result() -> ScreenSiteResult:
    run = AnalysisRun(
        technology="wind",
        status=AnalysisRunStatus.COMPLETED,
        started_at=START,
        finished_at=START + timedelta(hours=1),
    )
    spatial = SpatialRuleEngineResult(
        findings=(),
        excluded_geometry=None,
        remaining_geometry=None,
        initial_area_square_meters=1000.0,
        excluded_area_square_meters=0.0,
        available_area_square_meters=1000.0,
    )
    return ScreenSiteResult(analysis_run=run, spatial_result=spatial)


def _wind_simulation_result() -> WindSimulationResult:
    profile = EnergyProfile(samples=(EnergySample(START, 5.0),), source="test")
    return WindSimulationResult(
        no_wake_profile=profile,
        wake_profile=profile,
        wake_loss_mwh=0.0,
        wake_loss_fraction=0.0,
        turbine_profiles=(profile,),
    )


def _solar_simulation_result() -> SolarSimulationResult:
    profile = EnergyProfile(samples=(EnergySample(START, 3.0),), source="test")
    return SolarSimulationResult(
        dc_profile=profile,
        ac_profile=profile,
        inverter_loss_mwh=0.0,
        inverter_loss_fraction=0.0,
    )


def test_execute_forwards_project_and_result_without_any_simulation() -> None:
    generator = StubReportGenerator()
    report = GenerateAnalysisReport(generator).execute(_project(), _result())

    assert report == "rendered"
    assert generator.received is not None
    assert generator.received.wind_simulation_result is None
    assert generator.received.solar_simulation_result is None


def test_execute_forwards_optional_wind_simulation_result() -> None:
    generator = StubReportGenerator()
    wind_result = _wind_simulation_result()

    GenerateAnalysisReport(generator).execute(_project(), _result(), wind_result)

    assert generator.received is not None
    assert generator.received.wind_simulation_result is wind_result


def test_execute_forwards_optional_solar_simulation_result() -> None:
    generator = StubReportGenerator()
    solar_result = _solar_simulation_result()

    GenerateAnalysisReport(generator).execute(_project(), _result(), None, solar_result)

    assert generator.received is not None
    assert generator.received.solar_simulation_result is solar_result


def _hybrid_production_result() -> HybridProductionResult:
    profile = EnergyProfile(samples=(EnergySample(START, 8.0),), source="test")
    curtailment = CurtailmentResult(
        delivered_profile=profile,
        curtailed_energy_mwh=0.0,
        curtailed_energy_fraction=0.0,
        utilization_fraction=0.5,
    )
    return HybridProductionResult(aggregate_profile=profile, curtailment=curtailment)


def test_execute_forwards_optional_hybrid_result() -> None:
    generator = StubReportGenerator()
    hybrid_result = _hybrid_production_result()

    GenerateAnalysisReport(generator).execute(_project(), _result(), None, None, hybrid_result)

    assert generator.received is not None
    assert generator.received.hybrid_result is hybrid_result


def _battery_dispatch_result() -> BatteryDispatchResult:
    battery = Battery(
        manufacturer="Test Storage",
        model_name="TB-10",
        capacity_mwh=10.0,
        max_charge_power_mw=5.0,
        max_discharge_power_mw=5.0,
        round_trip_efficiency_percent=90.0,
        min_state_of_charge_fraction=0.0,
        max_state_of_charge_fraction=1.0,
        data_source="test",
        data_version="v1",
    )
    profile = EnergyProfile(samples=(EnergySample(START, 8.0),), source="test")
    return BatteryDispatcher().simulate(battery, profile, 5.0, 0.0)


def test_execute_forwards_optional_battery_dispatch_result() -> None:
    generator = StubReportGenerator()
    battery_result = _battery_dispatch_result()

    GenerateAnalysisReport(generator).execute(
        _project(), _result(), None, None, None, battery_result
    )

    assert generator.received is not None
    assert generator.received.battery_dispatch_result is battery_result
