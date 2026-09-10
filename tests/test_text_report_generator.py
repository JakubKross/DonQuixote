from datetime import UTC, datetime, timedelta

from renewable_planner.adapters.reporting import TextAnalysisReportGenerator
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


def _profile(power_mw: float) -> EnergyProfile:
    return EnergyProfile(samples=(EnergySample(START, power_mw),), source="test")


def _wind_simulation_result() -> WindSimulationResult:
    no_wake = _profile(10.0)
    with_wake = _profile(8.0)
    return WindSimulationResult(
        no_wake_profile=no_wake,
        wake_profile=with_wake,
        wake_loss_mwh=2.0,
        wake_loss_fraction=0.2,
        turbine_profiles=(with_wake,),
    )


def _solar_simulation_result() -> SolarSimulationResult:
    dc = _profile(5.0)
    ac = _profile(4.5)
    return SolarSimulationResult(
        dc_profile=dc,
        ac_profile=ac,
        inverter_loss_mwh=0.5,
        inverter_loss_fraction=0.1,
    )


def _hybrid_production_result() -> HybridProductionResult:
    aggregate = _profile(12.0)
    delivered = _profile(10.0)
    curtailment = CurtailmentResult(
        delivered_profile=delivered,
        curtailed_energy_mwh=2.0,
        curtailed_energy_fraction=2.0 / 12.0,
        utilization_fraction=0.8,
    )
    return HybridProductionResult(aggregate_profile=aggregate, curtailment=curtailment)


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
    profile = _profile(8.0)
    return BatteryDispatcher().simulate(
        battery, profile, target_power_mw=5.0, initial_state_of_charge_fraction=0.0
    )


def test_report_includes_placeholder_when_wind_simulation_was_not_run() -> None:
    report = TextAnalysisReportGenerator().generate(
        AnalysisReportRequest(project=_project(), result=_result())
    )

    assert "PRODUKCJA ENERGII (WIATR)" in report
    assert "PRODUKCJA ENERGII (PV)" in report
    assert "AGREGACJA HYBRYDOWA I PRZYŁĄCZE" in report
    assert "MAGAZYN ENERGII (BATERIA)" in report
    assert "nie uruchomiono" in report


def test_report_includes_aep_and_wake_losses_when_simulation_is_present() -> None:
    report = TextAnalysisReportGenerator().generate(
        AnalysisReportRequest(
            project=_project(),
            result=_result(),
            wind_simulation_result=_wind_simulation_result(),
        )
    )

    assert "AEP bez uwzględnienia wake: 10.00 MWh" in report
    assert "AEP z uwzględnieniem wake: 8.00 MWh" in report
    assert "Straty wake: 2.00 MWh (20.00%)" in report


def test_report_includes_dc_ac_and_inverter_losses_when_solar_simulation_is_present() -> None:
    report = TextAnalysisReportGenerator().generate(
        AnalysisReportRequest(
            project=_project(),
            result=_result(),
            solar_simulation_result=_solar_simulation_result(),
        )
    )

    assert "AEP DC (przed inwerterem): 5.00 MWh" in report
    assert "AEP AC (po inwerterze): 4.50 MWh" in report
    assert "Straty inwertera: 0.50 MWh (10.00%)" in report


def test_report_includes_curtailment_and_utilization_when_hybrid_result_is_present() -> None:
    report = TextAnalysisReportGenerator().generate(
        AnalysisReportRequest(
            project=_project(),
            result=_result(),
            hybrid_result=_hybrid_production_result(),
        )
    )

    assert "Produkcja łączna (przed ograniczeniem przyłącza): 12.00 MWh" in report
    assert "Dostarczone do sieci (po ograniczeniu przyłącza): 10.00 MWh" in report
    assert "Curtailment: 2.00 MWh (16.67%)" in report
    assert "Wykorzystanie przyłącza: 80.00%" in report


def test_report_includes_battery_dispatch_summary_when_result_is_present() -> None:
    report = TextAnalysisReportGenerator().generate(
        AnalysisReportRequest(
            project=_project(),
            result=_result(),
            battery_dispatch_result=_battery_dispatch_result(),
        )
    )

    assert "Naładowano: 3.00 MWh" in report
    assert "Straty magazynu: 0.30 MWh" in report
    assert "Energia dostarczona po wsparciu magazynu: 5.00 MWh" in report
    assert "Końcowy stan naładowania: 27.00%" in report
