import pytest

from renewable_planner.application.solar import (
    NoAvailableAreaError,
    SizeSolarArray,
    SizeSolarArrayCommand,
)
from renewable_planner.domain import (
    AnalysisRun,
    GroundCoverageRatio,
    ScreenSiteResult,
    SolarModule,
    SpatialRuleEngineResult,
)

MODULE = SolarModule(
    manufacturer="Test Solar",
    model_name="TS-400",
    rated_power_w=400,
    width_m=1.0,
    height_m=2.0,
    temperature_coefficient_pct_per_c=-0.4,
    data_source="test",
    data_version="v1",
)


def _result(available_area_square_meters: float) -> ScreenSiteResult:
    spatial = SpatialRuleEngineResult(
        findings=(),
        excluded_geometry=None,
        remaining_geometry=None,
        initial_area_square_meters=1000.0,
        excluded_area_square_meters=1000.0 - available_area_square_meters,
        available_area_square_meters=available_area_square_meters,
    )
    return ScreenSiteResult(analysis_run=AnalysisRun(), spatial_result=spatial)


def test_sizes_a_pv_array_from_the_available_area() -> None:
    use_case = SizeSolarArray()

    layout = use_case.execute(
        SizeSolarArrayCommand(
            screening_result=_result(1000.0),
            module=MODULE,
            ground_coverage_ratio=GroundCoverageRatio(0.4),
        )
    )

    # usable area = 400 m^2; module area = 2 m^2 -> 200 modules
    assert layout.module_count == 200


def test_raises_when_no_available_area_remains() -> None:
    use_case = SizeSolarArray()

    with pytest.raises(NoAvailableAreaError):
        use_case.execute(
            SizeSolarArrayCommand(
                screening_result=_result(0.0),
                module=MODULE,
                ground_coverage_ratio=GroundCoverageRatio(0.4),
            )
        )


def test_is_deterministic_for_the_same_inputs() -> None:
    use_case = SizeSolarArray()
    command = SizeSolarArrayCommand(
        screening_result=_result(1000.0),
        module=MODULE,
        ground_coverage_ratio=GroundCoverageRatio(0.4),
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first == second
