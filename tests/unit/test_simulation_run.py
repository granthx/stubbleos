"""Unit tests for simulation runner CLI and experiment execution."""

import json
from pathlib import Path

import pytest

from stubbleos.simulation.run import (
    instantiate_strategy,
    resolve_scenario_path,
    run_experiment,
)


def test_resolve_scenario_path() -> None:
    path = resolve_scenario_path("baseline-district")
    assert path.exists()
    assert path.name == "baseline-district.yaml"

    with pytest.raises(FileNotFoundError, match="Scenario configuration not found"):
        resolve_scenario_path("non-existent-scenario")


def test_instantiate_strategy() -> None:
    strat_a = instantiate_strategy("baseline_a")
    assert strat_a.name == "baseline_a"

    strat_b = instantiate_strategy("baseline-b")
    assert strat_b.name == "baseline_b"

    with pytest.raises(ValueError, match="Unknown strategy"):
        instantiate_strategy("unknown_strategy")


def test_run_experiment_execution_and_file_export(tmp_path: Path) -> None:
    out_dir = tmp_path / "results"
    report, runs = run_experiment(
        scenario_path="baseline-district",
        strategy_name="baseline_b",
        num_seeds=2,
        seed_start=2000,
        out_dir=out_dir,
    )

    assert report.scenario_name == "baseline-district"
    assert report.strategy_name == "baseline_b"
    assert len(runs) == 2
    assert report.num_seeds == 2
    assert report.is_synthetic is True

    result_dir = out_dir / "baseline-district_baseline_b"
    assert result_dir.exists()

    summary_file = result_dir / "summary.json"
    assert summary_file.exists()
    with open(summary_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["scenario_name"] == "baseline-district"
    assert "metrics" in data

    csv_file = result_dir / "runs.csv"
    assert csv_file.exists()
    lines = csv_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3  # Header + 2 rows
