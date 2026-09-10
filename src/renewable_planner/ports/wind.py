"""Ports for wind-farm simulation engines and wind-resource data."""

from typing import Protocol, runtime_checkable

from renewable_planner.domain.common import SpatialGeometry
from renewable_planner.domain.wind_layout import AvailableArea
from renewable_planner.domain.wind_resource import WindResourceTimeSeries
from renewable_planner.domain.wind_simulation import WindSimulationRequest, WindSimulationResult


@runtime_checkable
class AvailableAreaExtractor(Protocol):
    """Convert screened-site geometry into a wind-layout-ready available area."""

    def extract(self, geometry: SpatialGeometry) -> AvailableArea:
        """Return a metric ``AvailableArea`` built from the given geometry."""
        ...


@runtime_checkable
class WindFarmSimulator(Protocol):
    """Simulate a wind farm without exposing a third-party engine."""

    def simulate(self, request: WindSimulationRequest) -> WindSimulationResult:
        """Return aggregate and per-turbine hourly production profiles."""
        ...


@runtime_checkable
class WindResourceProvider(Protocol):
    """Provide a versioned hourly wind-resource time series."""

    def get_time_series(self) -> WindResourceTimeSeries:
        """Return the hourly wind speed and direction series with provenance."""
        ...
