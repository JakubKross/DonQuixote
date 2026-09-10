"""SizeSolarArray application use case."""

from dataclasses import dataclass

from renewable_planner.domain.solar_layout import (
    GroundCoverageRatio,
    SolarArrayLayout,
    SolarArraySizer,
)
from renewable_planner.domain.solar_module import SolarModule
from renewable_planner.domain.spatial_screening import ScreenSiteResult


class SizeSolarArrayError(RuntimeError):
    """Base class for readable SizeSolarArray application errors."""


class NoAvailableAreaError(SizeSolarArrayError):
    """Raised when screening left no available area for a PV array."""


@dataclass(frozen=True, slots=True)
class SizeSolarArrayCommand:
    """Validated input for sizing a PV array on a completed screening run."""

    screening_result: ScreenSiteResult
    module: SolarModule
    ground_coverage_ratio: GroundCoverageRatio


class SizeSolarArray:
    """Bridge a completed site screening into a deterministic PV-array size.

    Unlike wind turbine placement, no geometry port is needed: the
    ``ScreenSite`` use case already produces a scalar available area, which
    is exactly what area-based PV sizing requires.
    """

    def __init__(self, sizer: SolarArraySizer | None = None) -> None:
        self._sizer = sizer or SolarArraySizer()

    def execute(self, command: SizeSolarArrayCommand) -> SolarArrayLayout:
        """Size a PV array on the screening's available area."""
        area_m2 = command.screening_result.spatial_result.available_area_square_meters
        if area_m2 <= 0:
            raise NoAvailableAreaError("screening left no available area for a PV array")
        return self._sizer.generate(area_m2, command.module, command.ground_coverage_ratio)
