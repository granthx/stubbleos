"""Stochastic processes: rain shocks, machine breakdowns, and behavioral farmer burn decisions."""

from __future__ import annotations

import numpy as np

from stubbleos.core.types import FieldState
from stubbleos.simulation.config import ScenarioConfig
from stubbleos.simulation.model import SimulatedFarmer, SimulatedField, SimulatedMachine


class RainSchedule:
    """Deterministic rain shock schedule generated from seed."""

    def __init__(self, intervals: list[tuple[float, float]]) -> None:
        self.intervals = sorted(intervals)

    def is_raining(self, day: float) -> bool:
        return any(start <= day <= end for start, end in self.intervals)

    def next_rain_event(self, current_day: float) -> tuple[float, float] | None:
        for start, end in self.intervals:
            if end >= current_day:
                return (start, end)
        return None


def generate_rain_schedule(config: ScenarioConfig, rng: np.random.Generator) -> RainSchedule:
    """Generate discrete rain shock windows during the season."""
    severity = config.stochastic_parameters.rain_shock_severity
    if severity <= 0.0:
        return RainSchedule([])

    # Average 1 rain window per (1 / severity * 10) days
    intervals: list[tuple[float, float]] = []
    current_day = float(rng.uniform(3.0, 7.0))
    season_days = float(config.season_length_days)

    while current_day < season_days - 2.0:
        # Check if rain shock occurs in this period
        if rng.random() < severity:
            duration_hours = rng.uniform(
                config.stochastic_parameters.rain_duration_hours_min,
                config.stochastic_parameters.rain_duration_hours_max,
            )
            duration_days = duration_hours / 24.0
            end_day = min(season_days, current_day + duration_days)
            intervals.append((current_day, end_day))
            current_day = end_day + float(rng.uniform(3.0, 8.0))
        else:
            current_day += float(rng.uniform(3.0, 6.0))

    return RainSchedule(intervals)


def sample_machine_breakdown(
    machine: SimulatedMachine,
    operating_hours: float,
    config: ScenarioConfig,
    rng: np.random.Generator,
) -> float | None:
    """Returns repair_hours if a breakdown occurred during the operating period, else None."""
    # Convert daily breakdown rate to per-operating-hour rate (assuming ~8 operating hrs/day)
    rate_per_hour = config.stochastic_parameters.machine_breakdown_rate_per_day / 8.0
    prob_breakdown = 1.0 - float(np.exp(-rate_per_hour * operating_hours))

    if rng.random() < prob_breakdown:
        # Sample repair time from exponential distribution around mean repair hours
        mean_repair = config.stochastic_parameters.mean_repair_hours
        repair_hours = float(rng.exponential(scale=mean_repair))
        return max(2.0, min(repair_hours, 72.0))
    return None


def should_farmer_burn(
    farmer: SimulatedFarmer,
    field: SimulatedField,
    current_day: float,
    has_active_or_confirmed_booking: bool,
    rng: np.random.Generator,
) -> bool:
    """Evaluate whether a farmer decides to burn crop residue on a given day.

    Behavioral model:
    - If field is not yet harvested or already cleared/burned, no burn decision.
    - If machine is actively on site working, farmer does NOT burn.
    - Otherwise, desperation increases exponentially as days to sowing deadline diminish.
    - High trust extends patience; low trust accelerates burning.
    """
    if field.state != FieldState.HARVESTED_RESIDUE_PRESENT:
        return False

    if field.service_in_progress:
        return False

    days_to_deadline = field.sowing_deadline_day - current_day

    # If deadline has passed or deadline is tomorrow and no confirmed booking:
    if days_to_deadline <= 0:
        return True

    # If there is a confirmed booking and days_to_deadline > 1.5, farmer waits
    if has_active_or_confirmed_booking and days_to_deadline > 1.5:
        # Small probability of panic even with booking if trust is very low and deadline <= 2
        if days_to_deadline <= 2.0 and farmer.trust_score < 0.2:
            return bool(rng.random() < 0.15)
        return False

    # Uncoordinated / no confirmed booking situation:
    # Baseline burn pressure increases as deadline nears and trust is low
    urgency = max(0.0, (10.0 - days_to_deadline) / 10.0)  # 0 at 10 days out, 1.0 at deadline
    trust_discount = farmer.trust_score * 0.7  # trust dampens burning probability

    daily_burn_prob = (urgency**2.2) * (1.0 - trust_discount)

    # If days to deadline is <= 2 days, sharp spike
    if days_to_deadline <= 2.0:
        daily_burn_prob = max(daily_burn_prob, 0.45 * (1.0 - farmer.trust_score * 0.5))
    if days_to_deadline <= 1.0:
        daily_burn_prob = max(daily_burn_prob, 0.80 * (1.0 - farmer.trust_score * 0.3))

    return bool(rng.random() < min(1.0, daily_burn_prob))
