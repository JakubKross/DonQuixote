"""Pydantic request/response models for the web API.

Kept separate from the domain: these are wire-format shapes for one
interface, not the models ``ScreenSite`` operates on.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FindingSummary(BaseModel):
    """One constraint finding, shaped for JSON responses."""

    id: UUID
    constraint_id: UUID
    level: str
    status: str
    data_source: str
    data_version: str
    message: str


class ScreeningSummary(BaseModel):
    """Everything a client needs after creating or looking up a screening.

    Area/warning/finding fields are ``None`` until the run has a result
    (e.g. while ``status`` is ``pending``/``running``, or if it ``failed``
    before producing one) — mirrors the CLI's own summary, just as JSON.
    """

    id: UUID
    project_id: UUID
    site_id: UUID
    technology: str
    country: str
    status: str
    created_at: datetime | None = None
    error_message: str | None = None
    initial_area_square_meters: float | None = None
    excluded_area_square_meters: float | None = None
    available_area_square_meters: float | None = None
    warnings: int | None = None
    findings: list[FindingSummary] = Field(default_factory=list)


class ProfileSeries(BaseModel):
    """An hourly ``EnergyProfile`` as parallel arrays, ready to chart."""

    source: str
    timestamps: list[datetime]
    power_mw: list[float]
    total_energy_mwh: float


class TurbinePositionSummary(BaseModel):
    """One turbine candidate, in the screening's metric analysis CRS."""

    x_m: float
    y_m: float


class WindSimulationSummary(BaseModel):
    simulator: str
    no_wake_energy_mwh: float
    wake_energy_mwh: float
    wake_loss_mwh: float
    wake_loss_fraction: float
    wake_profile: ProfileSeries


class WindResult(BaseModel):
    """Outcome of ``POST /v1/screenings/{id}/turbine-layout``.

    ``simulation`` is ``None`` when no wind resource was uploaded, or when
    no turbine fitted the available area (nothing to simulate).
    """

    turbine_manufacturer: str
    turbine_model: str
    rated_power_kw: float
    rotor_diameter_m: float
    spacing_rotor_diameters: float
    grid_spacing_m: float | None
    crs: str
    turbine_count: int
    positions: list[TurbinePositionSummary]
    simulation: WindSimulationSummary | None = None


class SolarSimulationSummary(BaseModel):
    simulator: str
    dc_energy_mwh: float
    ac_energy_mwh: float
    inverter_loss_mwh: float
    inverter_loss_fraction: float
    ac_profile: ProfileSeries


class SolarResult(BaseModel):
    """Outcome of ``POST /v1/screenings/{id}/solar-array``."""

    module_manufacturer: str
    module_model: str
    ground_coverage_ratio: float
    module_count: int
    installed_capacity_kwp: float
    used_area_m2: float
    simulation: SolarSimulationSummary | None = None


class HybridResult(BaseModel):
    """Outcome of ``POST /v1/screenings/{id}/hybrid``."""

    grid_connection_limit_mw: float
    sources: list[str]
    aggregate_energy_mwh: float
    delivered_energy_mwh: float
    curtailed_energy_mwh: float
    curtailed_energy_fraction: float
    utilization_fraction: float
    aggregate_profile: ProfileSeries
    delivered_profile: ProfileSeries


class BatteryResult(BaseModel):
    """Outcome of ``POST /v1/screenings/{id}/battery-dispatch``."""

    battery_manufacturer: str
    battery_model: str
    target_power_mw: float
    initial_state_of_charge_fraction: float
    charged_energy_mwh: float
    discharged_energy_mwh: float
    round_trip_loss_mwh: float
    curtailed_energy_mwh: float
    final_state_of_charge_fraction: float
    delivered_profile: ProfileSeries
    state_of_charge_fraction: list[float]


class TechnologyResults(BaseModel):
    """Every technology result stored for one screening so far.

    Each field is ``None`` until its ``POST`` endpoint has run for this
    screening. Re-running wind or solar clears ``hybrid`` and ``battery``,
    and re-running hybrid clears ``battery``, so stored results never mix
    inputs from different runs.
    """

    screening_id: UUID
    wind: WindResult | None = None
    solar: SolarResult | None = None
    hybrid: HybridResult | None = None
    battery: BatteryResult | None = None
