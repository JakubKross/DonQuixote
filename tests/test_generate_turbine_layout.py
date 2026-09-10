import pytest

from renewable_planner.application.wind import (
    GenerateTurbineLayout,
    GenerateTurbineLayoutCommand,
    InvalidLayoutParametersError,
    NoAvailableAreaError,
)
from renewable_planner.domain import (
    AnalysisRun,
    AvailableArea,
    PowerCurvePoint,
    ScreenSiteResult,
    SpatialGeometry,
    SpatialRuleEngineResult,
    WindTurbine,
)

TURBINE = WindTurbine(
    manufacturer="Test Wind",
    model_name="TW-100",
    rated_power_kw=100,
    rotor_diameter_m=20,
    hub_height_m=80,
    cut_in_wind_speed_mps=3,
    rated_wind_speed_mps=10,
    cut_out_wind_speed_mps=25,
    power_curve=(PowerCurvePoint(3, 0), PowerCurvePoint(10, 100)),
    data_source="test",
    data_version="v1",
)
SQUARE_AREA = AvailableArea(exterior=((0, 0), (100, 0), (100, 100), (0, 100)))
SQUARE_GEOMETRY = SpatialGeometry("POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0))", "EPSG:2180")


class StubAvailableAreaExtractor:
    """Test double avoiding a dependency on Shapely in application tests."""

    def __init__(self, area: AvailableArea) -> None:
        self._area = area
        self.received: SpatialGeometry | None = None

    def extract(self, geometry: SpatialGeometry) -> AvailableArea:
        self.received = geometry
        return self._area


def _result(remaining_geometry: SpatialGeometry | None) -> ScreenSiteResult:
    spatial = SpatialRuleEngineResult(
        findings=(),
        excluded_geometry=None,
        remaining_geometry=remaining_geometry,
        initial_area_square_meters=10000.0,
        excluded_area_square_meters=0.0,
        available_area_square_meters=10000.0,
    )
    return ScreenSiteResult(analysis_run=AnalysisRun(), spatial_result=spatial)


def test_generates_positions_from_the_extracted_area_and_rotor_spacing() -> None:
    extractor = StubAvailableAreaExtractor(SQUARE_AREA)
    use_case = GenerateTurbineLayout(extractor)

    positions = use_case.execute(
        GenerateTurbineLayoutCommand(
            screening_result=_result(SQUARE_GEOMETRY),
            turbine=TURBINE,
            spacing_rotor_diameters=5,
        )
    )

    assert extractor.received == SQUARE_GEOMETRY
    assert positions
    assert all(SQUARE_AREA.contains((p.x_m, p.y_m)) for p in positions)


def test_raises_when_no_available_area_remains() -> None:
    use_case = GenerateTurbineLayout(StubAvailableAreaExtractor(SQUARE_AREA))

    with pytest.raises(NoAvailableAreaError):
        use_case.execute(
            GenerateTurbineLayoutCommand(
                screening_result=_result(None),
                turbine=TURBINE,
                spacing_rotor_diameters=5,
            )
        )


def test_extractor_is_not_called_when_no_available_area_remains() -> None:
    extractor = StubAvailableAreaExtractor(SQUARE_AREA)
    use_case = GenerateTurbineLayout(extractor)

    with pytest.raises(NoAvailableAreaError):
        use_case.execute(
            GenerateTurbineLayoutCommand(
                screening_result=_result(None),
                turbine=TURBINE,
                spacing_rotor_diameters=5,
            )
        )

    assert extractor.received is None


def test_rejects_non_positive_spacing_multiplier() -> None:
    use_case = GenerateTurbineLayout(StubAvailableAreaExtractor(SQUARE_AREA))

    with pytest.raises(InvalidLayoutParametersError):
        use_case.execute(
            GenerateTurbineLayoutCommand(
                screening_result=_result(SQUARE_GEOMETRY),
                turbine=TURBINE,
                spacing_rotor_diameters=0,
            )
        )


def test_is_deterministic_for_the_same_inputs() -> None:
    use_case = GenerateTurbineLayout(StubAvailableAreaExtractor(SQUARE_AREA))
    command = GenerateTurbineLayoutCommand(
        screening_result=_result(SQUARE_GEOMETRY),
        turbine=TURBINE,
        spacing_rotor_diameters=5,
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first == second
