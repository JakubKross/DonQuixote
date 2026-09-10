"""GenerateTurbineLayout application use case."""

from dataclasses import dataclass

from renewable_planner.domain.spatial_screening import ScreenSiteResult
from renewable_planner.domain.wind_layout import (
    GridTurbineCandidateGenerator,
    TurbinePosition,
    TurbineSpacing,
    WindLayoutValidationError,
)
from renewable_planner.domain.wind_turbine import WindTurbine
from renewable_planner.ports.wind import AvailableAreaExtractor


class GenerateTurbineLayoutError(RuntimeError):
    """Base class for readable GenerateTurbineLayout application errors."""


class NoAvailableAreaError(GenerateTurbineLayoutError):
    """Raised when screening left no available area for turbine placement."""


class InvalidLayoutParametersError(GenerateTurbineLayoutError):
    """Raised when spacing or turbine parameters cannot produce a layout."""


@dataclass(frozen=True, slots=True)
class GenerateTurbineLayoutCommand:
    """Validated input for generating deterministic turbine candidates."""

    screening_result: ScreenSiteResult
    turbine: WindTurbine
    spacing_rotor_diameters: float
    grid_spacing_m: float | None = None


class GenerateTurbineLayout:
    """Bridge a completed site screening into deterministic turbine candidates.

    The use case stays library-neutral: it only reads the standardized
    ``ScreenSiteResult`` produced by ``ScreenSite`` and delegates geometry
    conversion to the injected ``AvailableAreaExtractor`` port, so it never
    imports GeoPandas or Shapely directly.
    """

    def __init__(
        self,
        area_extractor: AvailableAreaExtractor,
        candidate_generator: GridTurbineCandidateGenerator | None = None,
    ) -> None:
        self._area_extractor = area_extractor
        self._candidate_generator = candidate_generator or GridTurbineCandidateGenerator()

    def execute(self, command: GenerateTurbineLayoutCommand) -> tuple[TurbinePosition, ...]:
        """Generate deterministic turbine candidates on the available area."""
        remaining = command.screening_result.spatial_result.remaining_geometry
        if remaining is None:
            raise NoAvailableAreaError("screening left no available area for turbine placement")

        area = self._area_extractor.extract(remaining)
        try:
            spacing = TurbineSpacing.from_rotor_diameters(
                command.spacing_rotor_diameters, command.turbine.rotor_diameter_m
            )
        except WindLayoutValidationError as error:
            raise InvalidLayoutParametersError(str(error)) from error

        return self._candidate_generator.generate(
            area, spacing, grid_spacing_m=command.grid_spacing_m
        )
