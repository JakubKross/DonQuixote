from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.domain import (
    SolarModule,
    SolarProductionModel,
    SolarProductionValidationError,
)

MODULE = SolarModule(
    manufacturer="Test Solar",
    model_name="TS-400",
    rated_power_w=400,
    width_m=1.0,
    height_m=1.7,
    temperature_coefficient_pct_per_c=-0.4,
    data_source="test",
    data_version="v1",
)
START = datetime(2026, 6, 1, 8, tzinfo=UTC)


def _timestamps(count: int) -> tuple[datetime, ...]:
    return tuple(START + timedelta(hours=index) for index in range(count))


def test_production_at_standard_test_conditions_equals_rated_power() -> None:
    profile = SolarProductionModel().generate(MODULE, _timestamps(1), (1000.0,), (25.0,))

    assert profile.samples[0].power_mw == pytest.approx(0.4 / 1000)


def test_production_is_zero_with_no_irradiance() -> None:
    profile = SolarProductionModel().generate(MODULE, _timestamps(1), (0.0,), (10.0,))

    assert profile.samples[0].power_mw == 0.0


def test_production_derates_above_stc_temperature() -> None:
    at_stc = SolarProductionModel().generate(MODULE, _timestamps(1), (1000.0,), (25.0,))
    hotter = SolarProductionModel().generate(MODULE, _timestamps(1), (1000.0,), (45.0,))

    assert hotter.samples[0].power_mw < at_stc.samples[0].power_mw


def test_production_clamps_negative_power_from_extreme_derating() -> None:
    profile = SolarProductionModel().generate(MODULE, _timestamps(1), (1000.0,), (300.0,))

    assert profile.samples[0].power_mw == 0.0


def test_production_applies_availability_and_losses() -> None:
    profile = SolarProductionModel().generate(
        MODULE,
        _timestamps(2),
        (1000.0, 1000.0),
        (25.0, 25.0),
        technical_availability=(1.0, 0.5),
        loss_factor=0.1,
    )

    assert profile.samples[0].power_mw == pytest.approx(0.4 / 1000 * 0.9)
    assert profile.samples[1].power_mw == pytest.approx(0.4 / 1000 * 0.5 * 0.9)


def test_production_preserves_timezone() -> None:
    profile = SolarProductionModel().generate(MODULE, _timestamps(1), (500.0,), (20.0,))

    assert profile.samples[0].timestamp.tzinfo is UTC


@pytest.mark.parametrize(
    ("timestamps", "irradiance", "temperature", "message"),
    [
        (_timestamps(1), (500.0, 500.0), (20.0,), "same length"),
        (_timestamps(1), (-1.0,), (20.0,), "non-negative"),
        (_timestamps(1), (float("nan"),), (20.0,), "finite"),
        (_timestamps(1), (500.0,), (float("inf"),), "finite"),
    ],
)
def test_production_rejects_invalid_inputs(
    timestamps: tuple[datetime, ...],
    irradiance: tuple[float, ...],
    temperature: tuple[float, ...],
    message: str,
) -> None:
    with pytest.raises(SolarProductionValidationError, match=message):
        SolarProductionModel().generate(MODULE, timestamps, irradiance, temperature)


def test_production_rejects_naive_timestamps() -> None:
    with pytest.raises(SolarProductionValidationError, match="timezone-aware"):
        SolarProductionModel().generate(MODULE, (datetime(2026, 6, 1, 8),), (500.0,), (20.0,))


def test_production_rejects_non_contiguous_hours() -> None:
    with pytest.raises(SolarProductionValidationError, match="contiguous"):
        SolarProductionModel().generate(
            MODULE,
            (START, START + timedelta(hours=2)),
            (500.0, 500.0),
            (20.0, 20.0),
        )
