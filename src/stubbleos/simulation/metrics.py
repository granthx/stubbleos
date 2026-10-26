"""Metrics calculation and multi-seed statistical aggregation pipeline."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import stats

from stubbleos.core.types import FieldState, LandholdingClass
from stubbleos.simulation.model import DistrictState
from stubbleos.simulation.strategy import CoordinationStrategy


def get_git_commit_hash() -> str:
    """Retrieve current git commit hash or fallback to unknown."""
    try:
        git_exe = shutil.which("git")
        if not git_exe:
            return "unknown"
        output = subprocess.check_output(  # noqa: S603
            [git_exe, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return output if output else "unknown"
    except Exception:
        return "unknown"


class SimulationRunMetrics(BaseModel):
    """Metrics computed from a single district simulation run."""

    model_config = ConfigDict(extra="forbid")

    scenario_name: str
    strategy_name: str
    seed: int
    config_hash: str
    git_commit: str = Field(default_factory=get_git_commit_hash)

    # Core required metrics
    pct_fields_cleared_before_deadline: float
    burn_events_per_1000_acres: float
    total_burn_events: int
    total_fields: int
    total_acres: float
    cleared_acres: float
    burned_acres: float
    machine_utilization_pct: float
    average_machine_idle_hours: float
    straw_tonnage_delivered: float
    buyer_order_fill_rate_pct: float
    avg_farmer_net_income_inr: float
    farmer_net_income_delta_vs_baseline_a: float = 0.0
    logistics_cost_per_ton_inr: float
    logistics_co2_kg_per_ton: float
    smallholder_clearance_pct: float
    largeholder_clearance_pct: float
    fairness_gap_pct: float
    overhead_messages_count: int
    overhead_llm_calls_count: int
    overhead_latency_ms: float
    is_synthetic: bool = True


class AggregatedMetric(BaseModel):
    """Statistical summary of a single scalar metric across random seeds."""

    model_config = ConfigDict(extra="forbid")

    mean: float
    std: float
    median: float
    min: float
    max: float
    ci_95_t: tuple[float, float]
    ci_95_bootstrap: tuple[float, float]


class AggregatedSimulationReport(BaseModel):
    """Complete summary report of aggregated simulation runs across N seeds."""

    model_config = ConfigDict(extra="forbid")

    scenario_name: str
    strategy_name: str
    num_seeds: int
    seed_list: list[int]
    config_hash: str
    git_commit: str
    metrics: dict[str, AggregatedMetric]
    is_synthetic: bool = True


def compute_run_metrics(
    state: DistrictState,
    strategy: CoordinationStrategy,
    scenario_name: str,
    seed: int,
    config_hash: str,
    season_length_days: int,
    baseline_a_avg_income: float | None = None,
) -> SimulationRunMetrics:
    """Compute all evaluation metrics for a single simulation run."""
    total_fields = len(state.fields)
    total_acres = state.total_acres

    # 1. % fields cleared before deadline
    cleared_before_deadline = sum(
        1
        for f in state.fields
        if f.is_cleared and f.cleared_at_day is not None and f.cleared_at_day <= f.sowing_deadline_day
    )
    pct_cleared_before_deadline = (
        round((cleared_before_deadline / total_fields) * 100.0, 2) if total_fields > 0 else 0.0
    )

    # 2. Burn events per 1000 acres
    total_burn_events = sum(1 for f in state.fields if f.state == FieldState.BURN_DETECTED)
    burn_events_per_1000_acres = (
        round((total_burn_events / total_acres) * 1000.0, 2) if total_acres > 0.0 else 0.0
    )

    # 3. Machine utilization and idle time
    total_season_hours = season_length_days * 24.0
    total_machines = len(state.machines)
    total_op_hours = sum(m.operating_hours for m in state.machines)
    total_capacity_hours = total_machines * total_season_hours

    machine_utilization_pct = (
        round((total_op_hours / total_capacity_hours) * 100.0, 2) if total_capacity_hours > 0.0 else 0.0
    )
    avg_idle_hours = (
        round(sum(m.idle_hours for m in state.machines) / total_machines, 2) if total_machines > 0 else 0.0
    )

    # 4. Straw tonnage delivered and buyer fill rate
    tonnes_delivered = round(state.delivered_straw_tonnes, 2)
    total_buyer_demand = sum(b.tonnes_required for b in state.buyers)
    buyer_fill_rate_pct = (
        round((tonnes_delivered / total_buyer_demand) * 100.0, 2) if total_buyer_demand > 0.0 else 100.0
    )

    # 5. Farmer net income
    avg_net_income = (
        round(sum(f.net_income_inr for f in state.farmers) / len(state.farmers), 2) if state.farmers else 0.0
    )
    net_income_delta = (
        round(avg_net_income - baseline_a_avg_income, 2) if baseline_a_avg_income is not None else 0.0
    )

    # 6. Logistics cost and CO2 per delivered ton (haversine-based)
    total_truck_km = sum(t.total_km_travelled for t in state.trucks)
    total_logistics_cost = sum(t.total_km_travelled * t.cost_per_km_inr for t in state.trucks)
    delivered_divisor = max(1.0, tonnes_delivered)

    logistics_cost_per_ton = round(total_logistics_cost / delivered_divisor, 2)
    # Diesel emission factor: 1.42 kg CO2 per truck-km for medium-duty trucks
    logistics_co2_kg_per_ton = round((total_truck_km * 1.42) / delivered_divisor, 2)

    # 7. Fairness gap between smallholders (marginal/small) and largeholders (medium/large)
    farmer_map = {f.farmer_id: f for f in state.farmers}
    small_classes = {LandholdingClass.MARGINAL, LandholdingClass.SMALL}
    large_classes = {LandholdingClass.SEMI_MEDIUM, LandholdingClass.MEDIUM, LandholdingClass.LARGE}

    small_fields = [f for f in state.fields if farmer_map[f.farmer_id].landholding_class in small_classes]
    large_fields = [f for f in state.fields if farmer_map[f.farmer_id].landholding_class in large_classes]

    small_cleared = sum(
        1
        for f in small_fields
        if f.is_cleared and f.cleared_at_day is not None and f.cleared_at_day <= f.sowing_deadline_day
    )
    large_cleared = sum(
        1
        for f in large_fields
        if f.is_cleared and f.cleared_at_day is not None and f.cleared_at_day <= f.sowing_deadline_day
    )

    small_pct = round((small_cleared / len(small_fields)) * 100.0, 2) if small_fields else 100.0
    large_pct = round((large_cleared / len(large_fields)) * 100.0, 2) if large_fields else 100.0
    fairness_gap_pct = round(large_pct - small_pct, 2)

    # 8. Coordination overhead
    overhead = strategy.get_overhead_metrics()

    return SimulationRunMetrics(
        scenario_name=scenario_name,
        strategy_name=strategy.name,
        seed=seed,
        config_hash=config_hash,
        pct_fields_cleared_before_deadline=pct_cleared_before_deadline,
        burn_events_per_1000_acres=burn_events_per_1000_acres,
        total_burn_events=total_burn_events,
        total_fields=total_fields,
        total_acres=round(total_acres, 2),
        cleared_acres=round(state.cleared_acres, 2),
        burned_acres=round(state.burned_acres, 2),
        machine_utilization_pct=machine_utilization_pct,
        average_machine_idle_hours=avg_idle_hours,
        straw_tonnage_delivered=tonnes_delivered,
        buyer_order_fill_rate_pct=buyer_fill_rate_pct,
        avg_farmer_net_income_inr=avg_net_income,
        farmer_net_income_delta_vs_baseline_a=net_income_delta,
        logistics_cost_per_ton_inr=logistics_cost_per_ton,
        logistics_co2_kg_per_ton=logistics_co2_kg_per_ton,
        smallholder_clearance_pct=small_pct,
        largeholder_clearance_pct=large_pct,
        fairness_gap_pct=fairness_gap_pct,
        overhead_messages_count=overhead["messages_count"],
        overhead_llm_calls_count=overhead["llm_calls_count"],
        overhead_latency_ms=overhead["total_planning_latency_ms"],
        is_synthetic=True,
    )


def compute_confidence_intervals(values: list[float]) -> tuple[tuple[float, float], tuple[float, float]]:
    """Computes both parametric Student's t-interval and bootstrap percentile 95% CI.

    Returns:
        ((t_low, t_high), (boot_low, boot_high))
    """
    arr = np.array(values, dtype=np.float64)
    n = len(arr)

    # Constant array or single value edge case
    if n < 2 or np.all(arr == arr[0]):
        v = float(arr[0])
        return ((v, v), (v, v))

    # 1. Student's t-distribution 95% confidence interval
    mean = float(np.mean(arr))
    se = float(stats.sem(arr))
    t_ci = stats.t.interval(0.95, df=n - 1, loc=mean, scale=se)
    ci_t = (round(float(t_ci[0]), 3), round(float(t_ci[1]), 3))

    # 2. Non-parametric bootstrap percentile interval (10,000 resamples with fixed seed for determinism)
    boot_rng = np.random.default_rng(42)
    boot_means = [float(np.mean(boot_rng.choice(arr, size=n, replace=True))) for _ in range(10000)]
    ci_boot = (
        round(float(np.percentile(boot_means, 2.5)), 3),
        round(float(np.percentile(boot_means, 97.5)), 3),
    )

    return (ci_t, ci_boot)


def aggregate_seed_metrics(
    runs: list[SimulationRunMetrics],
    scenario_name: str,
    strategy_name: str,
    config_hash: str,
) -> AggregatedSimulationReport:
    """Aggregate N runs across seeds into a statistical report with mean and 95% CIs."""
    if not runs:
        raise ValueError("Cannot aggregate empty list of simulation runs.")

    metric_keys = [
        "pct_fields_cleared_before_deadline",
        "burn_events_per_1000_acres",
        "cleared_acres",
        "burned_acres",
        "machine_utilization_pct",
        "average_machine_idle_hours",
        "straw_tonnage_delivered",
        "buyer_order_fill_rate_pct",
        "avg_farmer_net_income_inr",
        "farmer_net_income_delta_vs_baseline_a",
        "logistics_cost_per_ton_inr",
        "logistics_co2_kg_per_ton",
        "smallholder_clearance_pct",
        "largeholder_clearance_pct",
        "fairness_gap_pct",
        "overhead_messages_count",
        "overhead_llm_calls_count",
        "overhead_latency_ms",
    ]

    aggregated: dict[str, AggregatedMetric] = {}

    for key in metric_keys:
        vals = [float(getattr(r, key)) for r in runs]
        ci_t, ci_boot = compute_confidence_intervals(vals)
        aggregated[key] = AggregatedMetric(
            mean=round(float(np.mean(vals)), 3),
            std=round(float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0, 3),
            median=round(float(np.median(vals)), 3),
            min=round(float(np.min(vals)), 3),
            max=round(float(np.max(vals)), 3),
            ci_95_t=ci_t,
            ci_95_bootstrap=ci_boot,
        )

    seeds = [r.seed for r in runs]
    git_commit = runs[0].git_commit

    return AggregatedSimulationReport(
        scenario_name=scenario_name,
        strategy_name=strategy_name,
        num_seeds=len(runs),
        seed_list=seeds,
        config_hash=config_hash,
        git_commit=git_commit,
        metrics=aggregated,
        is_synthetic=True,
    )
