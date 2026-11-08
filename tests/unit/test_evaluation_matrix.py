"""Unit tests for evaluation matrix and benchmarks."""

from __future__ import annotations

from pathlib import Path

from stubbleos.evals.benchmarks import (
    benchmark_api_endpoints,
    benchmark_cpsat_scheduler,
    benchmark_eventbus_throughput,
    benchmark_pii_redaction,
    run_all_benchmarks,
)
from stubbleos.evals.matrix import (
    execute_evaluation_matrix,
    generate_markdown_summary,
    update_results_files,
)


def test_benchmark_cpsat_scheduler():
    results = benchmark_cpsat_scheduler(sizes=[5, 10])
    assert len(results) == 2
    assert results[0]["num_jobs"] == 5
    assert results[0]["solve_latency_ms"] >= 0.0
    assert results[0]["solver_status"] in ("OPTIMAL", "FEASIBLE")


def test_benchmark_eventbus_throughput():
    res = benchmark_eventbus_throughput(event_count=50)
    assert res["events_dispatched"] == 50
    assert res["events_received"] == 50
    assert res["throughput_events_per_sec"] > 0.0


def test_benchmark_pii_redaction():
    res = benchmark_pii_redaction(iterations=50)
    assert res["redaction_calls"] == 50
    assert res["throughput_ops_per_sec"] > 0.0


def test_benchmark_api_endpoints():
    res = benchmark_api_endpoints()
    assert "GET /healthz" in res
    assert "GET /readyz" in res
    assert "GET /api/v1/fields" in res
    assert all(lat >= 0.0 for lat in res.values())


def test_run_all_benchmarks():
    data = run_all_benchmarks()
    assert "scheduler_latency" in data
    assert "event_bus_throughput" in data
    assert "pii_redaction_throughput" in data
    assert "api_endpoint_latency_ms" in data


def test_evaluation_matrix_execution(tmp_path: Path):
    # Execute 1 scenario, 2 strategies, 1 seed for fast unit test
    matrix = execute_evaluation_matrix(
        scenarios=["baseline-district"],
        strategies=["baseline_a", "stubbleos_centralized"],
        num_seeds=1,
        seed_start=2000,
        out_dir=tmp_path / "results",
    )

    assert len(matrix.reports) == 2
    assert ("baseline-district", "baseline_a") in matrix.reports
    assert ("baseline-district", "stubbleos_centralized") in matrix.reports

    md = generate_markdown_summary(matrix)
    assert "Scenario: `baseline-district`" in md
    assert "`baseline_a`" in md
    assert "`stubbleos_centralized`" in md

    # Test update_results_files
    update_results_files(matrix, root_dir=tmp_path)
    assert (tmp_path / "results" / "evaluation_matrix.json").exists()
    assert (tmp_path / "results" / "evaluation_summary.md").exists()
    assert (tmp_path / "docs" / "RESULTS.md").exists()
