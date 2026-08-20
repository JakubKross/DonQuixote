from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.domain import (
    PowerCurvePoint,
    WindProductionModel,
    WindProductionValidationError,
    WindTurbine,
)

TURBINE = WindTurbine(
    manufacturer="Test Wind",
    model_name="TW-100",
    rated_power_kw=100,
    rotor_diameter_m=100,
    hub_height_m=100,
    cut_in_wind_speed_mps=3,
    rated_wind_speed_mps=10,
    cut_out_wind_speed_mps=25,
    power_curve=(
        PowerCurvePoint(3, 0),
        PowerCurvePoint(5, 50),
        PowerCurvePoint(10, 100),
        PowerCurvePoint(25, 0),
    ),
    data_source="test",
    data_version="v1",
)
START = datetime(2026, 1, 1, 8, tzinfo=UTC)


def _timestamps(count: int) -> tuple[datetime, ...]:
    return tuple(START + timedelta(hours=index) for index in range(count))


def test_production_handles_cut_in_rated_and_cut_out_boundaries() -> None:
    profile = WindProductionModel().generate(
        TURBINE,
        _timestamps(5),
        (2, 3, 10, 24.9, 25),
    )

    assert [sample.power_mw for sample in profile.samples] == pytest.approx(
        [0, 0, 0.1, 0.00066666666666667, 0]
    )
    assert profile.total_energy_mwh == pytest.approx(0.10066666666666667)


def test_production_interpolates_linearly_between_curve_points() -> None:
    profile = WindProductionModel().generate(TURBINE, _timestamps(1), (4,))

    assert profile.samples[0].power_mw == pytest.approx(0.025)


def test_production_applies_availability_and_losses() -> None:
    profile = WindProductionModel().generate(
        TURBINE,
        _timestamps(2),
        (10, 10),
        technical_availability=(1.0, 0.5),
        loss_factor=0.1,
    )

    assert [sample.power_mw for sample in profile.samples] == pytest.approx([0.09, 0.045])


def test_production_preserves_timezone() -> None:
    profile = WindProductionModel().generate(TURBINE, _timestamps(1), (10,))

    assert profile.samples[0].timestamp.tzinfo is UTC


@pytest.mark.parametrize(
    ("timestamps", "speeds", "availability", "losses", "message"),
    [
        (_timestamps(1), (10, 10), 1.0, 0.0, "same length"),
        (_timestamps(2), (10, 10), (1.0,), 0.0, "same length"),
        (_timestamps(1), (-1,), 1.0, 0.0, "non-negative"),
        (_timestamps(1), (float("nan"),), 1.0, 0.0, "finite"),
        (_timestamps(1), (10,), 1.1, 0.0, "between 0 and 1"),
        (_timestamps(1), (10,), 1.0, -0.1, "between 0 and 1"),
    ],
)
def test_production_rejects_invalid_inputs(
    timestamps: tuple[datetime, ...],
    speeds: tuple[float, ...],
    availability: float | tuple[float, ...],
    losses: float,
    message: str,
) -> None:
    with pytest.raises(WindProductionValidationError, match=message):
        WindProductionModel().generate(
            TURBINE,
            timestamps,
            speeds,
            technical_availability=availability,
            loss_factor=losses,
        )


def test_production_rejects_naive_timestamps() -> None:
    with pytest.raises(WindProductionValidationError, match="timezone-aware"):
        WindProductionModel().generate(TURBINE, (datetime(2026, 1, 1, 8),), (10,))


def test_production_rejects_non_contiguous_hours() -> None:
    with pytest.raises(WindProductionValidationError, match="contiguous"):
        WindProductionModel().generate(
            TURBINE,
            (START, START + timedelta(hours=2)),
            (10, 10),
        )
