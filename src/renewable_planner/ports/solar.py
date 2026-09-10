"""Ports for PV-array simulation engines and solar-resource data."""

from typing import Protocol, runtime_checkable

from renewable_planner.domain.solar_resource import SolarResourceTimeSeries
from renewable_planner.domain.solar_simulation import SolarSimulationRequest, SolarSimulationResult


@runtime_checkable
class SolarResourceProvider(Protocol):
    """Provide a versioned hourly solar-resource time series."""

    def get_time_series(self) -> SolarResourceTimeSeries:
        """Return the hourly irradiance and temperature series with provenance."""
        ...


@runtime_checkable
class SolarArraySimulator(Protocol):
    """Simulate a PV array without exposing a third-party engine."""

    def simulate(self, request: SolarSimulationRequest) -> SolarSimulationResult:
        """Return the DC and AC hourly production profiles for the array."""
        ...
