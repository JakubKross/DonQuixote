"""Convert technology use-case results into API response models, and back.

The wind/solar/hybrid/battery endpoints in ``api/app.py`` store their
results as these JSON-ready models (see
``adapters.memory_repositories.InMemoryTechnologyResultRepository``). Later
steps of the chain need only the hourly profiles back — hybrid aggregates
the wind/solar profiles, battery dispatch runs on the hybrid aggregate — so
``to_energy_profile`` is the only conversion in the other direction.
"""

from __future__ import annotations

from collections.abc import Sequence

from renewable_planner.api.schemas import (
    BatteryResult,
    HybridResult,
    ProfileSeries,
    SolarResult,
    SolarSimulationSummary,
    TurbinePositionSummary,
    WindResult,
    WindSimulationSummary,
)
from renewable_planner.domain import (
    Battery,
    BatteryDispatchResult,
    EnergyProfile,
    EnergySample,
    HybridProductionResult,
    SolarArrayLayout,
    SolarModule,
    SolarSimulationResult,
    TurbinePosition,
    WindSimulationResult,
    WindTurbine,
)


def profile_series(profile: EnergyProfile) -> ProfileSeries:
    return ProfileSeries(
        source=profile.source,
        timestamps=[sample.timestamp for sample in profile.samples],
        power_mw=[sample.power_mw for sample in profile.samples],
        total_energy_mwh=profile.total_energy_mwh,
    )


def to_energy_profile(series: ProfileSeries) -> EnergyProfile:
    return EnergyProfile(
        samples=tuple(
            EnergySample(timestamp, power_mw)
            for timestamp, power_mw in zip(series.timestamps, series.power_mw, strict=True)
        ),
        source=series.source,
    )


def wind_result(
    turbine: WindTurbine,
    spacing_rotor_diameters: float,
    grid_spacing_m: float | None,
    crs: str,
    positions: Sequence[TurbinePosition],
    simulation: WindSimulationResult | None,
    simulator: str,
) -> WindResult:
    return WindResult(
        turbine_manufacturer=turbine.manufacturer,
        turbine_model=turbine.model_name,
        rated_power_kw=turbine.rated_power_kw,
        rotor_diameter_m=turbine.rotor_diameter_m,
        spacing_rotor_diameters=spacing_rotor_diameters,
        grid_spacing_m=grid_spacing_m,
        crs=crs,
        turbine_count=len(positions),
        positions=[TurbinePositionSummary(x_m=p.x_m, y_m=p.y_m) for p in positions],
        simulation=(
            None
            if simulation is None
            else WindSimulationSummary(
                simulator=simulator,
                no_wake_energy_mwh=simulation.no_wake_profile.total_energy_mwh,
                wake_energy_mwh=simulation.wake_profile.total_energy_mwh,
                wake_loss_mwh=simulation.wake_loss_mwh,
                wake_loss_fraction=simulation.wake_loss_fraction,
                wake_profile=profile_series(simulation.wake_profile),
            )
        ),
    )


def solar_result(
    module: SolarModule,
    ground_coverage_ratio: float,
    layout: SolarArrayLayout,
    simulation: SolarSimulationResult | None,
    simulator: str,
) -> SolarResult:
    return SolarResult(
        module_manufacturer=module.manufacturer,
        module_model=module.model_name,
        ground_coverage_ratio=ground_coverage_ratio,
        module_count=layout.module_count,
        installed_capacity_kwp=layout.installed_capacity_w / 1000,
        used_area_m2=layout.used_area_m2,
        simulation=(
            None
            if simulation is None
            else SolarSimulationSummary(
                simulator=simulator,
                dc_energy_mwh=simulation.dc_profile.total_energy_mwh,
                ac_energy_mwh=simulation.ac_profile.total_energy_mwh,
                inverter_loss_mwh=simulation.inverter_loss_mwh,
                inverter_loss_fraction=simulation.inverter_loss_fraction,
                ac_profile=profile_series(simulation.ac_profile),
            )
        ),
    )


def hybrid_result(
    result: HybridProductionResult,
    grid_connection_limit_mw: float,
    sources: Sequence[str],
) -> HybridResult:
    curtailment = result.curtailment
    return HybridResult(
        grid_connection_limit_mw=grid_connection_limit_mw,
        sources=list(sources),
        aggregate_energy_mwh=result.aggregate_profile.total_energy_mwh,
        delivered_energy_mwh=curtailment.delivered_profile.total_energy_mwh,
        curtailed_energy_mwh=curtailment.curtailed_energy_mwh,
        curtailed_energy_fraction=curtailment.curtailed_energy_fraction,
        utilization_fraction=curtailment.utilization_fraction,
        aggregate_profile=profile_series(result.aggregate_profile),
        delivered_profile=profile_series(curtailment.delivered_profile),
    )


def battery_result(
    battery: Battery,
    target_power_mw: float,
    initial_state_of_charge_fraction: float,
    result: BatteryDispatchResult,
) -> BatteryResult:
    return BatteryResult(
        battery_manufacturer=battery.manufacturer,
        battery_model=battery.model_name,
        target_power_mw=target_power_mw,
        initial_state_of_charge_fraction=initial_state_of_charge_fraction,
        charged_energy_mwh=result.charged_energy_mwh,
        discharged_energy_mwh=result.discharged_energy_mwh,
        round_trip_loss_mwh=result.round_trip_loss_mwh,
        curtailed_energy_mwh=result.curtailed_energy_mwh,
        final_state_of_charge_fraction=result.final_state_of_charge_fraction,
        delivered_profile=profile_series(result.delivered_profile),
        state_of_charge_fraction=[sample.state_of_charge_fraction for sample in result.samples],
    )
