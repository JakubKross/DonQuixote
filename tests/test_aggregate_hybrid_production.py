from datetime import UTC, datetime, timedelta

import pytest

from renewable_planner.application.hybrid import (
    AggregateHybridProduction,
    AggregateHybridProductionCommand,
)
from renewable_planner.domain import EnergyProfile, EnergySample, GridConnectionLimit

START = datetime(2026, 1, 1, tzinfo=UTC)


def _profile(source: str, *powers: float) -> EnergyProfile:
    samples = tuple(
        EnergySample(START + timedelta(hours=index), power) for index, power in enumerate(powers)
    )
    return EnergyProfile(samples=samples, source=source)


def test_aggregates_wind_and_solar_profiles_before_curtailment() -> None:
    wind = _profile("wind", 3.0, 4.0)
    solar = _profile("solar", 1.0, 2.0)
    use_case = AggregateHybridProduction()

    result = use_case.execute(
        AggregateHybridProductionCommand(
            profiles=(wind, solar),
            connection_limit=GridConnectionLimit(10.0),
        )
    )

    assert [s.power_mw for s in result.aggregate_profile.samples] == [4.0, 6.0]
    assert [s.power_mw for s in result.curtailment.delivered_profile.samples] == [4.0, 6.0]
    assert result.curtailment.curtailed_energy_mwh == 0.0


def test_curtails_the_aggregate_to_the_connection_limit() -> None:
    wind = _profile("wind", 3.0, 4.0)
    solar = _profile("solar", 1.0, 2.0)
    use_case = AggregateHybridProduction()

    result = use_case.execute(
        AggregateHybridProductionCommand(
            profiles=(wind, solar),
            connection_limit=GridConnectionLimit(5.0),
        )
    )

    # aggregate = [4.0, 6.0]; limit = 5.0 -> delivered = [4.0, 5.0]
    assert [s.power_mw for s in result.curtailment.delivered_profile.samples] == [4.0, 5.0]
    assert result.curtailment.curtailed_energy_mwh == pytest.approx(1.0)


def test_command_rejects_empty_profiles() -> None:
    with pytest.raises(ValueError, match="at least one"):
        AggregateHybridProductionCommand(
            profiles=(),
            connection_limit=GridConnectionLimit(5.0),
        )


def test_command_rejects_mismatched_timestamps() -> None:
    wind = _profile("wind", 3.0, 4.0)
    misaligned_solar = EnergyProfile(
        samples=(EnergySample(START + timedelta(hours=5), 1.0),),
        source="solar",
    )

    with pytest.raises(ValueError, match="same timestamps"):
        AggregateHybridProductionCommand(
            profiles=(wind, misaligned_solar),
            connection_limit=GridConnectionLimit(5.0),
        )


def test_is_deterministic_for_the_same_inputs() -> None:
    command = AggregateHybridProductionCommand(
        profiles=(_profile("wind", 3.0), _profile("solar", 1.0)),
        connection_limit=GridConnectionLimit(5.0),
    )
    use_case = AggregateHybridProduction()

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first == second
