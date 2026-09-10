"""Deterministic hourly battery dispatch: charge with surplus, discharge to fill gaps.

Kept independent of ``wind``, ``solar`` and ``grid`` (see AGENTS.md): the
dispatcher only needs an hourly power profile and a plain target power in
MW — not a ``grid`` module's connection-limit type. The ``hybrid``
application layer is what decides which profile and target to pass in.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from renewable_planner.domain.battery import Battery
from renewable_planner.domain.common import require_aware
from renewable_planner.domain.energy_profile import EnergyProfile, EnergySample


class BatteryDispatchValidationError(ValueError):
    """Raised when a battery dispatch request is invalid."""


@dataclass(frozen=True, slots=True)
class BatteryDispatchSample:
    """One hour's charge/discharge decision and resulting state of charge."""

    timestamp: datetime
    charge_power_mw: float
    discharge_power_mw: float
    state_of_charge_fraction: float
    delivered_power_mw: float
    curtailed_power_mw: float


@dataclass(frozen=True, slots=True)
class BatteryDispatchResult:
    """Standardized result of simulating one battery against a power profile."""

    samples: tuple[BatteryDispatchSample, ...]
    delivered_profile: EnergyProfile
    charged_energy_mwh: float
    discharged_energy_mwh: float
    round_trip_loss_mwh: float
    curtailed_energy_mwh: float
    final_state_of_charge_fraction: float


class BatteryDispatcher:
    """Charge a battery with production surplus and discharge to fill gaps.

    Round-trip losses are applied entirely on charge (a deliberate
    first-version simplification): charging at ``p`` MW for one hour stores
    ``p * round_trip_efficiency`` MWh, and discharging returns exactly what
    is withdrawn from storage.
    """

    def simulate(
        self,
        battery: Battery,
        profile: EnergyProfile,
        target_power_mw: float,
        initial_state_of_charge_fraction: float,
    ) -> BatteryDispatchResult:
        """Simulate hourly dispatch of ``battery`` against ``profile``."""
        target = _require_finite_non_negative(target_power_mw, "target_power_mw")
        soc_mwh = _initial_state_of_charge_mwh(battery, initial_state_of_charge_fraction)
        efficiency = battery.round_trip_efficiency_percent / 100
        min_soc_mwh = battery.min_state_of_charge_fraction * battery.capacity_mwh
        max_soc_mwh = battery.max_state_of_charge_fraction * battery.capacity_mwh

        samples: list[BatteryDispatchSample] = []
        delivered_samples: list[EnergySample] = []
        charged_mwh = 0.0
        discharged_mwh = 0.0
        stored_mwh = 0.0

        for index, sample in enumerate(profile.samples):
            try:
                require_aware(sample.timestamp, f"samples[{index}].timestamp")
            except ValueError as error:
                raise BatteryDispatchValidationError(str(error)) from error
            power = sample.power_mw
            surplus = max(0.0, power - target)
            deficit = max(0.0, target - power)

            charge_power_mw = 0.0
            discharge_power_mw = 0.0
            if surplus > 0:
                headroom_mwh = max(0.0, max_soc_mwh - soc_mwh)
                max_chargeable_mw = headroom_mwh / efficiency if efficiency > 0 else 0.0
                charge_power_mw = min(surplus, battery.max_charge_power_mw, max_chargeable_mw)
                stored_this_hour_mwh = charge_power_mw * efficiency
                soc_mwh += stored_this_hour_mwh
                charged_mwh += charge_power_mw
                stored_mwh += stored_this_hour_mwh
                # Delivery is capped at the target regardless of how much of
                # the surplus the battery could absorb: whatever the battery
                # does not store is curtailed, never exported above target.
                delivered_power_mw = target
                curtailed_power_mw = surplus - charge_power_mw
            elif deficit > 0:
                available_mwh = max(0.0, soc_mwh - min_soc_mwh)
                discharge_power_mw = min(deficit, battery.max_discharge_power_mw, available_mwh)
                soc_mwh -= discharge_power_mw
                discharged_mwh += discharge_power_mw
                delivered_power_mw = power + discharge_power_mw
                curtailed_power_mw = 0.0
            else:
                delivered_power_mw = power
                curtailed_power_mw = 0.0

            state_of_charge_fraction = soc_mwh / battery.capacity_mwh
            samples.append(
                BatteryDispatchSample(
                    timestamp=sample.timestamp,
                    charge_power_mw=charge_power_mw,
                    discharge_power_mw=discharge_power_mw,
                    state_of_charge_fraction=state_of_charge_fraction,
                    delivered_power_mw=delivered_power_mw,
                    curtailed_power_mw=curtailed_power_mw,
                )
            )
            delivered_samples.append(EnergySample(sample.timestamp, delivered_power_mw))

        try:
            delivered_profile = EnergyProfile(
                samples=tuple(delivered_samples),
                source=f"{profile.source} (battery-assisted delivery)",
            )
        except ValueError as error:
            raise BatteryDispatchValidationError(str(error)) from error

        return BatteryDispatchResult(
            samples=tuple(samples),
            delivered_profile=delivered_profile,
            charged_energy_mwh=charged_mwh,
            discharged_energy_mwh=discharged_mwh,
            round_trip_loss_mwh=charged_mwh - stored_mwh,
            curtailed_energy_mwh=sum(s.curtailed_power_mw for s in samples),
            final_state_of_charge_fraction=(
                samples[-1].state_of_charge_fraction
                if samples
                else initial_state_of_charge_fraction
            ),
        )


def _require_finite_non_negative(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BatteryDispatchValidationError(f"{field_name} must be a number")
    if not math.isfinite(value) or value < 0:
        raise BatteryDispatchValidationError(f"{field_name} must be finite and non-negative")
    return float(value)


def _initial_state_of_charge_mwh(battery: Battery, initial_fraction: float) -> float:
    if (
        isinstance(initial_fraction, bool)
        or not isinstance(initial_fraction, (int, float))
        or not math.isfinite(initial_fraction)
    ):
        raise BatteryDispatchValidationError("initial_state_of_charge_fraction must be a number")
    if not (
        battery.min_state_of_charge_fraction
        <= initial_fraction
        <= battery.max_state_of_charge_fraction
    ):
        raise BatteryDispatchValidationError(
            "initial_state_of_charge_fraction must be within the battery's allowed "
            f"range [{battery.min_state_of_charge_fraction}, "
            f"{battery.max_state_of_charge_fraction}]"
        )
    return float(initial_fraction) * battery.capacity_mwh
