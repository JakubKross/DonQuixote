from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.domain import (
    WindResourceSample,
    WindResourceTimeSeries,
    WindResourceValidationError,
)

START = datetime(2026, 1, 1, tzinfo=UTC)


def _sample(hours: int, speed: float = 5.0, direction: float = 180.0) -> WindResourceSample:
    return WindResourceSample(START + timedelta(hours=hours), speed, direction)


def test_series_exposes_ordered_speed_and_direction_tuples() -> None:
    series = WindResourceTimeSeries(
        samples=(_sample(0, 4.0, 180.0), _sample(1, 6.0, 190.0)),
        source="stacja testowa",
        version="v1",
    )

    assert series.timestamps == (START, START + timedelta(hours=1))
    assert series.wind_speeds_mps == (4.0, 6.0)
    assert series.wind_directions_deg == (180.0, 190.0)


def test_series_rejects_empty_samples() -> None:
    with pytest.raises(WindResourceValidationError, match="empty"):
        WindResourceTimeSeries(samples=(), source="stacja testowa", version="v1")


def test_series_rejects_non_contiguous_samples() -> None:
    with pytest.raises(WindResourceValidationError, match="contiguous"):
        WindResourceTimeSeries(
            samples=(_sample(0), _sample(2)),
            source="stacja testowa",
            version="v1",
        )


def test_series_rejects_empty_source_or_version() -> None:
    with pytest.raises(WindResourceValidationError, match="source"):
        WindResourceTimeSeries(samples=(_sample(0),), source=" ", version="v1")
    with pytest.raises(WindResourceValidationError, match="version"):
        WindResourceTimeSeries(samples=(_sample(0),), source="stacja testowa", version=" ")


def test_sample_rejects_naive_timestamp() -> None:
    with pytest.raises(WindResourceValidationError, match="timezone-aware"):
        WindResourceSample(datetime(2026, 1, 1), 5.0, 180.0)


def test_sample_rejects_timestamp_not_aligned_to_full_hour() -> None:
    with pytest.raises(WindResourceValidationError, match="full hour"):
        WindResourceSample(START + timedelta(minutes=30), 5.0, 180.0)


@pytest.mark.parametrize(
    ("speed", "message"),
    [(-1.0, "non-negative"), (float("nan"), "finite")],
)
def test_sample_rejects_invalid_wind_speed(speed: float, message: str) -> None:
    with pytest.raises(WindResourceValidationError, match=message):
        WindResourceSample(START, speed, 180.0)


@pytest.mark.parametrize(
    ("direction", "message"),
    [(-1.0, r"\[0, 360\)"), (360.0, r"\[0, 360\)"), (float("nan"), "finite")],
)
def test_sample_rejects_invalid_wind_direction(direction: float, message: str) -> None:
    with pytest.raises(WindResourceValidationError, match=message):
        WindResourceSample(START, 5.0, direction)
