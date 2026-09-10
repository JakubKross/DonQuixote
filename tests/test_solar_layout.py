import pytest

from renewable_planner.domain import (
    GroundCoverageRatio,
    SolarArraySizer,
    SolarLayoutValidationError,
    SolarModule,
)

MODULE = SolarModule(
    manufacturer="Test Solar",
    model_name="TS-400",
    rated_power_w=400,
    width_m=1.0,
    height_m=2.0,  # area = 2 m^2
    temperature_coefficient_pct_per_c=-0.4,
    data_source="test",
    data_version="v1",
)


def test_sizer_fits_the_expected_module_count() -> None:
    layout = SolarArraySizer().generate(1000.0, MODULE, GroundCoverageRatio(0.4))

    # usable area = 400 m^2; module area = 2 m^2 -> 200 modules
    assert layout.module_count == 200
    assert layout.used_area_m2 == pytest.approx(400.0)
    assert layout.installed_capacity_w == pytest.approx(200 * 400)


def test_sizer_is_deterministic() -> None:
    sizer = SolarArraySizer()
    gcr = GroundCoverageRatio(0.35)

    first = sizer.generate(750.0, MODULE, gcr)
    second = sizer.generate(750.0, MODULE, gcr)

    assert first == second


def test_sizer_returns_zero_modules_when_area_too_small() -> None:
    layout = SolarArraySizer().generate(1.0, MODULE, GroundCoverageRatio(0.5))

    assert layout.module_count == 0
    assert layout.installed_capacity_w == 0.0
    assert layout.used_area_m2 == 0.0


@pytest.mark.parametrize("area", [-1.0, 0.0, float("nan"), float("inf")])
def test_sizer_rejects_invalid_area(area: float) -> None:
    with pytest.raises(SolarLayoutValidationError):
        SolarArraySizer().generate(area, MODULE, GroundCoverageRatio(0.4))


@pytest.mark.parametrize("value", [0.0, -0.1, 1.1, float("nan")])
def test_ground_coverage_ratio_rejects_out_of_range_values(value: float) -> None:
    with pytest.raises(SolarLayoutValidationError):
        GroundCoverageRatio(value)


def test_ground_coverage_ratio_accepts_full_coverage() -> None:
    assert GroundCoverageRatio(1.0).value == 1.0
