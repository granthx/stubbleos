"""Comprehensive evaluation matrix runner for StubbleOS across scenarios and strategies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from stubbleos.simulation.metrics import AggregatedSimulationReport
from stubbleos.simulation.run import run_experiment

DEFAULT_SCENARIOS = [
    "baseline-district",
    "machine-scarce",
    "rain-shock",
    "low-trust",
]

DEFAULT_STRATEGIES = [
    "baseline_a",
    "baseline_b",
    "stubbleos_centralized",
    "stubbleos_decentralized",
]


class EvaluationMatrixResult:
    """Encapsulates the full evaluation grid results."""

    def __init__(self) -> None:
        # (scenario, strategy) -> AggregatedSimulationReport
        self.reports: dict[tuple[str, str], AggregatedSimulationReport] = {}

    def add_report(self, scenario: str, strategy: str, report: AggregatedSimulationReport) -> None:
        self.reports[(scenario, strategy)] = report

    def to_dict(self) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for (scen, strat), rep in self.reports.items():
            if scen not in output:
                output[scen] = {}
            output[scen][strat] = rep.model_dump()
        return output


def execute_evaluation_matrix(
    scenarios: list[str] = DEFAULT_SCENARIOS,
    strategies: list[str] = DEFAULT_STRATEGIES,
    num_seeds: int = 5,
    seed_start: int = 1000,
    out_dir: str | Path | None = "results",
) -> EvaluationMatrixResult:
    """Execute the full cross-product of scenarios and strategies."""
    matrix = EvaluationMatrixResult()

    if out_dir is not None:
        Path(out_dir).mkdir(parents=True, exist_ok=True)

    for scen in scenarios:
        print("\n=======================================================")
        print(f"Evaluating Scenario: {scen} across {len(strategies)} strategies (seeds={num_seeds})")
        print("=======================================================")

        # Run baseline_a first to establish reference income
        ref_income: float | None = None
        if "baseline_a" in strategies:
            print(f"\n>>> Running {scen} with strategy='baseline_a'...")
            rep_a, _ = run_experiment(
                scenario_path=scen,
                strategy_name="baseline_a",
                num_seeds=num_seeds,
                seed_start=seed_start,
                out_dir=out_dir,
            )
            matrix.add_report(scen, "baseline_a", rep_a)
            ref_income = rep_a.metrics["avg_farmer_net_income_inr"].mean

        # Run remaining strategies
        for strat in strategies:
            if strat == "baseline_a":
                continue
            print(f"\n>>> Running {scen} with strategy='{strat}'...")
            rep, _ = run_experiment(
                scenario_path=scen,
                strategy_name=strat,
                num_seeds=num_seeds,
                seed_start=seed_start,
                out_dir=out_dir,
                baseline_a_reference_income=ref_income,
            )
            matrix.add_report(scen, strat, rep)

    return matrix


def generate_markdown_summary(matrix: EvaluationMatrixResult) -> str:
    """Generate GitHub-flavored markdown comparison tables from matrix results."""
    lines: list[str] = []
    lines.append("# StubbleOS Evaluation Matrix & Benchmark Results\n")
    lines.append(
        "> **Note**: All results are generated from reproducible, seeded discrete-event simulation runs.\n"
    )

    # Group by scenario
    scenarios = sorted({scen for (scen, _) in matrix.reports})

    for scen in scenarios:
        lines.append(f"### Scenario: `{scen}`\n")
        lines.append(
            "| Strategy | Clearance Rate (%) | Burns / 1k Acres | Burn Reduction vs Baseline A | Fairness Gap (%) | Straw Delivered (t) | Machine Util (%) | Overhead Latency (ms) |"
        )
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        base_burn = 0.0
        if (scen, "baseline_a") in matrix.reports:
            base_burn = matrix.reports[(scen, "baseline_a")].metrics["burn_events_per_1000_acres"].mean

        for strat in ["baseline_a", "baseline_b", "stubbleos_centralized", "stubbleos_decentralized"]:
            if (scen, strat) not in matrix.reports:
                continue
            rep = matrix.reports[(scen, strat)]
            m = rep.metrics

            clearance = f"{m['pct_fields_cleared_before_deadline'].mean:.1f}%"
            burns = f"{m['burn_events_per_1000_acres'].mean:.2f}"

            if strat == "baseline_a" or base_burn == 0.0:
                reduction_str = "Reference (0.0%)"
            else:
                curr_burn = m["burn_events_per_1000_acres"].mean
                red_pct = ((base_burn - curr_burn) / base_burn) * 100.0 if base_burn > 0 else 0.0
                reduction_str = f"{red_pct:+.1f}%"

            fairness = f"{m['fairness_gap_pct'].mean:.2f}%"
            straw = f"{m['straw_tonnage_delivered'].mean:.1f}"
            util = f"{m['machine_utilization_pct'].mean:.1f}%"
            lat = f"{m['overhead_latency_ms'].mean:.1f}"

            lines.append(
                f"| `{strat}` | {clearance} | {burns} | {reduction_str} | {fairness} | {straw} | {util} | {lat} |"
            )
        lines.append("\n")

    return "\n".join(lines)


def update_results_files(matrix: EvaluationMatrixResult, root_dir: Path | None = None) -> None:
    """Write results to results/evaluation_matrix.json, docs/RESULTS.md, and update README.md."""
    if root_dir is None:
        root_dir = Path(".")

    results_dir = root_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write evaluation_matrix.json
    matrix_json_path = results_dir / "evaluation_matrix.json"
    with open(matrix_json_path, "w", encoding="utf-8") as f:
        json.dump(matrix.to_dict(), f, indent=2)

    # 2. Generate markdown summary
    md_content = generate_markdown_summary(matrix)
    summary_path = results_dir / "evaluation_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 3. Write docs/RESULTS.md
    docs_dir = root_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    docs_results_path = docs_dir / "RESULTS.md"
    with open(docs_results_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 4. Update README.md Results section
    readme_path = root_dir / "README.md"
    if readme_path.exists():
        with open(readme_path, encoding="utf-8") as f:
            readme_text = f.read()

        results_marker = "## Results"
        capabilities_marker = "## Core Architecture & Capabilities"

        if results_marker in readme_text and capabilities_marker in readme_text:
            before = readme_text.split(results_marker)[0]
            after = readme_text.split(capabilities_marker)[1]

            new_results_section = (
                f"{results_marker}\n\n"
                f"The results below are produced by reproducible multi-seed simulation runs (`make results`):\n\n"
                f"{md_content}\n"
                f"{capabilities_marker}"
            )
            updated_readme = before + new_results_section + after

            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(updated_readme)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run StubbleOS multi-scenario evaluation matrix.")
    parser.add_argument("--seeds", "-n", type=int, default=5, help="Number of seeds per cell (default: 5)")
    parser.add_argument("--seed-start", type=int, default=1000, help="Starting random seed (default: 1000)")
    parser.add_argument("--out", "-o", default="results", help="Output directory")
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=DEFAULT_SCENARIOS,
        help="List of scenarios to evaluate",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=DEFAULT_STRATEGIES,
        help="List of strategies to evaluate",
    )
    args = parser.parse_args()

    matrix = execute_evaluation_matrix(
        scenarios=args.scenarios,
        strategies=args.strategies,
        num_seeds=args.seeds,
        seed_start=args.seed_start,
        out_dir=args.out,
    )

    update_results_files(matrix)
    print("\n[EVALUATION MATRIX] Complete! Results written to results/, docs/RESULTS.md, and README.md.")


if __name__ == "__main__":
    main()
