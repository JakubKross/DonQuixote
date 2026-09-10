"""Deterministic preliminary PV-array sizing on an available area.

Unlike wind turbines (discrete points needing minimum spacing), PV modules
are tiled densely in rows. The standard preliminary sizing approach is an
area-based estimate using a ground coverage ratio (GCR) — the fraction of
the available area actually usable for modules once row spacing, access
paths and setbacks are accounted for. This keeps the ``solar`` module
independent of ``wind``'s point-and-polygon layout model.
"""

import math
from dataclasses import dataclass

from renewable_planner.domain.solar_module import SolarModule


class SolarLayoutValidationError(ValueError):
    """Raised when a PV-array sizing input is invalid."""


@dataclass(frozen=True, slots=True)
class GroundCoverageRatio:
    """Fraction of the available area usable for densely tiled modules."""

    value: float

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise SolarLayoutValidationError("value must be a number")
        if not math.isfinite(self.value) or not 0 < self.value <= 1:
            raise SolarLayoutValidationError("value must be finite and within (0, 1]")


@dataclass(frozen=True, slots=True)
class SolarArrayLayout:
    """Deterministic result of area-based PV-array sizing."""

    module_count: int
    installed_capacity_w: float
    used_area_m2: float


class SolarArraySizer:
    """Estimate how many modules fit a metric available area."""

    def generate(
        self,
        available_area_m2: float,
        module: SolarModule,
        ground_coverage_ratio: GroundCoverageRatio,
    ) -> SolarArrayLayout:
        """Return the deterministic module count fitting the usable area."""
        area = _finite_positive(available_area_m2, "available_area_m2")
        if not isinstance(module, SolarModule):
            raise SolarLayoutValidationError("module must be a SolarModule")
        if not isinstance(ground_coverage_ratio, GroundCoverageRatio):
            raise SolarLayoutValidationError("ground_coverage_ratio must be a GroundCoverageRatio")

        usable_area_m2 = area * ground_coverage_ratio.value
        module_count = math.floor(usable_area_m2 / module.area_m2 + 1e-12)
        used_area_m2 = module_count * module.area_m2
        installed_capacity_w = module_count * module.rated_power_w
        return SolarArrayLayout(
            module_count=module_count,
            installed_capacity_w=installed_capacity_w,
            used_area_m2=used_area_m2,
        )


def _finite_positive(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SolarLayoutValidationError(f"{name} must be a number")
    if not math.isfinite(value) or value <= 0:
        raise SolarLayoutValidationError(f"{name} must be finite and greater than zero")
    return float(value)
