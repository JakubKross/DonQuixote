from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.domain import (
    SolarResourceSample,
    SolarResourceTimeSeries,
    SolarResourceValidationError,
)

START = datetime(2026, 6, 1, tzinfo=UTC)


def _sample(
    hours: int, irradiance: float = 500.0, temperature: float = 20.0
) -> SolarResourceSample:
    return SolarResourceSample(START + timedelta(hours=hours), irradiance, temperature)


def test_series_exposes_ordered_irradiance_and_temperature_tuples() -> None:
    series = SolarResourceTimeSeries(
        samples=(_sample(0, 200.0, 15.0), _sample(1, 500.0, 18.0)),
        source="stacja testowa",
        version="v1",
    )

    assert series.timestamps == (START, START + timedelta(hours=1))
    assert series.poa_irradiance_w_per_m2 == (200.0, 500.0)
    assert series.ambient_temperature_c == (15.0, 18.0)


def test_series_rejects_empty_samples() -> None:
    with pytest.raises(SolarResourceValidationError, match="empty"):
        SolarResourceTimeSeries(samples=(), source="stacja testowa", version="v1")


def test_series_rejects_non_contiguous_samples() -> None:
    with pytest.raises(SolarResourceValidationError, match="contiguous"):
        SolarResourceTimeSeries(
            samples=(_sample(0), _sample(2)),
            source="stacja testowa",
            version="v1",
        )


def test_series_rejects_empty_source_or_version() -> None:
    with pytest.raises(SolarResourceValidationError, match="source"):
        SolarResourceTimeSeries(samples=(_sample(0),), source=" ", version="v1")
    with pytest.raises(SolarResourceValidationError, match="version"):
        SolarResourceTimeSeries(samples=(_sample(0),), source="stacja testowa", version=" ")


def test_sample_rejects_naive_timestamp() -> None:
    with pytest.raises(SolarResourceValidationError, match="timezone-aware"):
        SolarResourceSample(datetime(2026, 6, 1), 500.0, 20.0)


def test_sample_rejects_timestamp_not_aligned_to_full_hour() -> None:
    with pytest.raises(SolarResourceValidationError, match="full hour"):
        SolarResourceSample(START + timedelta(minutes=30), 500.0, 20.0)


@pytest.mark.parametrize(
    ("irradiance", "message"),
    [(-1.0, "non-negative"), (float("nan"), "finite")],
)
def test_sample_rejects_invalid_irradiance(irradiance: float, message: str) -> None:
    with pytest.raises(SolarResourceValidationError, match=message):
        SolarResourceSample(START, irradiance, 20.0)


def test_sample_rejects_non_finite_temperature() -> None:
    with pytest.raises(SolarResourceValidationError, match="finite"):
        SolarResourceSample(START, 500.0, float("inf"))
