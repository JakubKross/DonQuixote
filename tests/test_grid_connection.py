from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.domain import (
    EnergyProfile,
    EnergySample,
    GridConnectionLimit,
    GridConnectionLimiter,
    GridConnectionValidationError,
)

START = datetime(2026, 1, 1, tzinfo=UTC)


def _profile(*powers: float) -> EnergyProfile:
    samples = tuple(
        EnergySample(START + timedelta(hours=index), power) for index, power in enumerate(powers)
    )
    return EnergyProfile(samples=samples, source="test")


def test_limit_rejects_non_positive_values() -> None:
    with pytest.raises(GridConnectionValidationError):
        GridConnectionLimit(0.0)
    with pytest.raises(GridConnectionValidationError):
        GridConnectionLimit(-1.0)


def test_apply_passes_through_when_below_the_limit() -> None:
    profile = _profile(1.0, 2.0, 3.0)
    result = GridConnectionLimiter().apply(profile, GridConnectionLimit(10.0))

    assert result.delivered_profile.total_energy_mwh == pytest.approx(6.0)
    assert result.curtailed_energy_mwh == 0.0
    assert result.curtailed_energy_fraction == 0.0


def test_apply_clips_power_above_the_limit() -> None:
    profile = _profile(1.0, 5.0, 10.0)
    result = GridConnectionLimiter().apply(profile, GridConnectionLimit(4.0))

    assert [s.power_mw for s in result.delivered_profile.samples] == [1.0, 4.0, 4.0]
    assert result.curtailed_energy_mwh == pytest.approx(1.0 + 6.0)
    assert result.curtailed_energy_fraction == pytest.approx(7.0 / 16.0)


def test_apply_reports_utilization_fraction() -> None:
    profile = _profile(4.0, 4.0)  # exactly at the limit for both hours
    result = GridConnectionLimiter().apply(profile, GridConnectionLimit(4.0))

    assert result.utilization_fraction == pytest.approx(1.0)


def test_apply_reports_zero_utilization_for_zero_production() -> None:
    profile = _profile(0.0, 0.0)
    result = GridConnectionLimiter().apply(profile, GridConnectionLimit(4.0))

    assert result.utilization_fraction == 0.0
    assert result.curtailed_energy_fraction == 0.0
