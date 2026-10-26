"""CLI and programmatic runner for district simulation experiments."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Callable
from pathlib import Path

from stubbleos.simulation.config import ScenarioConfig
from stubbleos.simulation.metrics import (
    AggregatedSimulationReport,
    SimulationRunMetrics,
    aggregate_seed_metrics,
    compute_run_metrics,
)
from stubbleos.simulation.simulator import DistrictSimulator
from stubbleos.simulation.strategy import (
    BaselineAStrategy,
    BaselineBStrategy,
    CoordinationStrategy,
    StubbleOSCentralizedStrategy,
    StubbleOSDecentralizedStrategy,
)

STRATEGY_REGISTRY: dict[str, Callable[[], CoordinationStrategy]] = {
    "baseline_a": BaselineAStrategy,
    "baseline_b": BaselineBStrategy,
    "stubbleos_centralized": StubbleOSCentralizedStrategy,
    "stubbleos_decentralized": StubbleOSDecentralizedStrategy,
}


def resolve_scenario_path(scenario_arg: str) -> Path:
    """Resolve scenario argument to a valid file path."""
    p = Path(scenario_arg)
    if p.exists():
        return p

    # Try appending .yaml
    p_yaml = Path(f"{scenario_arg}.yaml")
    if p_yaml.exists():
        return p_yaml

    # Try searching in scenarios/ directory
    in_scenarios = Path("scenarios") / scenario_arg
    if in_scenarios.exists():
        return in_scenarios

    in_scenarios_yaml = Path("scenarios") / f"{scenario_arg}.yaml"
    if in_scenarios_yaml.exists():
        return in_scenarios_yaml

    raise FileNotFoundError(f"Scenario configuration not found: {scenario_arg}")


def instantiate_strategy(name: str) -> CoordinationStrategy:
    """Instantiate a coordination strategy by name."""
    norm_name = name.lower().replace("-", "_")
    if norm_name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[norm_name]()


def run_experiment(
    scenario_path: str | Path,
    strategy_name: str,
    num_seeds: int = 30,
    seed_start: int = 1000,
    out_dir: str | Path | None = None,
    baseline_a_reference_income: float | None = None,
) -> tuple[AggregatedSimulationReport, list[SimulationRunMetrics]]:
    """Execute simulation experiment over N seeds, computing run metrics and aggregate CIs."""
    path = resolve_scenario_path(str(scenario_path))
    config = ScenarioConfig.from_yaml_file(path)
    config_hash = config.config_hash()

    runs: list[SimulationRunMetrics] = []
    seeds = [seed_start + i for i in range(num_seeds)]

    for seed in seeds:
        strat = instantiate_strategy(strategy_name)
        sim = DistrictSimulator(config=config, strategy=strat, seed=seed)
        final_state = sim.run()

        run_metric = compute_run_metrics(
            state=final_state,
            strategy=strat,
            scenario_name=config.name,
            seed=seed,
            config_hash=config_hash,
            season_length_days=config.season_length_days,
            baseline_a_avg_income=baseline_a_reference_income,
        )
        runs.append(run_metric)

    report = aggregate_seed_metrics(
        runs=runs,
        scenario_name=config.name,
        strategy_name=strategy_name,
        config_hash=config_hash,
    )

    if out_dir is not None:
        target_dir = Path(out_dir) / f"{config.name}_{strategy_name}"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Write summary.json
        summary_path = target_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2)

        # Write runs.csv
        csv_path = target_dir / "runs.csv"
        if runs:
            fieldnames = list(runs[0].model_dump().keys())
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in runs:
                    writer.writerow(r.model_dump())

    return report, runs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run reproducible StubbleOS district simulation experiments."
    )
    parser.add_argument(
        "--scenario",
        "-s",
        required=True,
        help="Scenario name or YAML file path (e.g. baseline-district, machine-scarce)",
    )
    parser.add_argument(
        "--strategy",
        "-t",
        required=True,
        help="Coordination strategy: baseline_a, baseline_b, stubbleos_centralized, stubbleos_decentralized",
    )
    parser.add_argument(
        "--seeds",
        "-n",
        type=int,
        default=30,
        help="Number of random seeds to evaluate (default: 30)",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=1000,
        help="Initial seed integer (default: 1000)",
    )
    parser.add_argument(
        "--out",
        "-o",
        default="results",
        help="Output directory for JSON and CSV result files (default: results/)",
    )
    parser.add_argument(
        "--baseline-a-income",
        type=float,
        default=None,
        help="Optional baseline A average income reference for calculating delta",
    )

    args = parser.parse_args()

    print(
        f"[SIMULATION] Starting scenario='{args.scenario}' strategy='{args.strategy}' "
        f"seeds={args.seeds} (seed_start={args.seed_start})"
    )

    report, runs = run_experiment(
        scenario_path=args.scenario,
        strategy_name=args.strategy,
        num_seeds=args.seeds,
        seed_start=args.seed_start,
        out_dir=args.out,
        baseline_a_reference_income=args.baseline_a_income,
    )

    target_dir = Path(args.out) / f"{report.scenario_name}_{report.strategy_name}"
    print(f"[SIMULATION] Completed {len(runs)} seeds. Results written to {target_dir}")
    print(f"[SIMULATION] Config hash: {report.config_hash} | Git commit: {report.git_commit}")
    print("[SIMULATION] Key Aggregated Metrics (Mean ± Std | 95% t-CI | 95% Bootstrap CI):")
    for key, agg in report.metrics.items():
        print(
            f"  - {key}: {agg.mean:.2f} ± {agg.std:.2f} "
            f"(t-CI: [{agg.ci_95_t[0]:.2f}, {agg.ci_95_t[1]:.2f}], "
            f"boot-CI: [{agg.ci_95_bootstrap[0]:.2f}, {agg.ci_95_bootstrap[1]:.2f}])"
        )


if __name__ == "__main__":
    main()
