from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.domain import EnergyProfile, EnergySample, sum_profiles


def test_profile_calculates_energy_from_hourly_power() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    profile = EnergyProfile(
        samples=(
            EnergySample(start, 2.5),
            EnergySample(start + timedelta(hours=1), 3.0),
        ),
        source="model testowy v1",
    )

    assert profile.total_energy_mwh == 5.5


def test_profile_rejects_non_contiguous_samples() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="contiguous"):
        EnergyProfile(
            samples=(
                EnergySample(start, 1.0),
                EnergySample(start + timedelta(hours=2), 1.0),
            ),
            source="model testowy v1",
        )


def test_sample_rejects_negative_power() -> None:
    with pytest.raises(ValueError, match="negative"):
        EnergySample(datetime(2026, 1, 1, tzinfo=UTC), -0.1)


def test_sum_profiles_adds_power_at_matching_timestamps() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    first = EnergyProfile(
        samples=(EnergySample(start, 1.0), EnergySample(start + timedelta(hours=1), 2.0)),
        source="turbine 0",
    )
    second = EnergyProfile(
        samples=(EnergySample(start, 3.0), EnergySample(start + timedelta(hours=1), 4.0)),
        source="turbine 1",
    )

    total = sum_profiles((first, second), source="farm total")

    assert total.source == "farm total"
    assert [sample.power_mw for sample in total.samples] == [4.0, 6.0]


def test_sum_profiles_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="empty"):
        sum_profiles((), source="farm total")
