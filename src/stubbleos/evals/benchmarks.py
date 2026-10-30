"""Performance, latency, and throughput benchmarks for StubbleOS components."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any
from uuid import uuid4

from stubbleos.core.events import Event, EventPayload, InMemoryEventBus, register_event
from stubbleos.core.privacy import redact_text
from stubbleos.core.types import LandholdingClass, MachineType
from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
    SchedulerConfig,
    solve_schedule,
)

try:

    @register_event("benchmark.ping")
    class BenchmarkPing(EventPayload):
        counter: int
        data: str
except ValueError:
    from stubbleos.core.events import get_payload_type

    BenchmarkPing = get_payload_type("benchmark.ping")  # type: ignore[assignment,misc]


def benchmark_cpsat_scheduler(sizes: list[int] | None = None) -> list[dict[str, Any]]:
    """Benchmark CP-SAT scheduler solve latency across increasing batch sizes."""
    if sizes is None:
        sizes = [10, 25, 50, 100]
    results: list[dict[str, Any]] = []

    for n in sizes:
        jobs = [
            JobRequest(
                field_id=uuid4(),
                farmer_id=uuid4(),
                landholding_class=LandholdingClass.SMALL if i % 2 == 0 else LandholdingClass.MEDIUM,
                area_acres=4.0 + (i % 5),
                earliest_start_hour=0.0,
                deadline_hour=72.0 + (i % 24),
                center_lat=30.80 + (i * 0.005),
                center_lon=75.80 + (i * 0.005),
                eligible_machine_types=list(MachineType),
            )
            for i in range(n)
        ]

        machine_count = max(5, n // 3)
        machines = [
            MachineResource(
                machine_id=uuid4(),
                machine_type=MachineType.SUPER_SEEDER if i % 2 == 0 else MachineType.HAPPY_SEEDER,
                capacity_acres_per_hour=1.2,
                hourly_cost_inr=1200.0,
                current_lat=30.85,
                current_lon=75.85,
                available_from_hour=0.0,
            )
            for i in range(machine_count)
        ]

        cfg = SchedulerConfig(time_limit_seconds=2.0, random_seed=42)

        start = time.perf_counter()
        solution = solve_schedule(jobs, machines, config=cfg)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        results.append(
            {
                "num_jobs": n,
                "num_machines": machine_count,
                "assigned_jobs": len(solution.assignments),
                "unassigned_jobs": len(solution.unassigned_field_ids),
                "solve_latency_ms": round(elapsed_ms, 2),
                "solver_status": solution.solver_status,
            }
        )

    return results


def benchmark_eventbus_throughput(event_count: int = 5000) -> dict[str, Any]:
    """Benchmark EventBus in-memory event dispatch throughput (events/sec)."""
    import asyncio

    bus = InMemoryEventBus()
    received_count = 0

    async def on_ping(event: Event) -> None:
        nonlocal received_count
        received_count += 1

    bus.subscribe("benchmark.ping", on_ping)

    async def run_dispatch() -> float:
        start = time.perf_counter()
        for i in range(event_count):
            await bus.emit(BenchmarkPing(counter=i, data="test benchmark payload"), source="benchmark")
        return time.perf_counter() - start

    elapsed_sec = asyncio.run(run_dispatch())
    rate = event_count / elapsed_sec if elapsed_sec > 0 else 0.0
    return {
        "events_dispatched": event_count,
        "events_received": received_count,
        "elapsed_seconds": round(elapsed_sec, 4),
        "throughput_events_per_sec": round(rate, 2),
    }


def benchmark_pii_redaction(iterations: int = 2000) -> dict[str, Any]:
    """Benchmark PII redaction throughput on phone numbers and names."""
    sample_text = (
        "Farmer Gurpreet Singh from village Raikot with phone +91 9876543210 "
        "requested Happy Seeder booking for 8.5 acres before 2026-11-05."
    )

    start = time.perf_counter()
    for _ in range(iterations):
        redact_text(sample_text)
    elapsed_sec = time.perf_counter() - start

    rate = iterations / elapsed_sec if elapsed_sec > 0 else 0.0
    return {
        "redaction_calls": iterations,
        "elapsed_seconds": round(elapsed_sec, 4),
        "throughput_ops_per_sec": round(rate, 2),
    }


def benchmark_api_endpoints() -> dict[str, Any]:
    """Benchmark FastAPI internal endpoint latency using TestClient."""
    from fastapi.testclient import TestClient

    from stubbleos.api.app import create_app
    from stubbleos.core.config import Settings

    settings = Settings(_env_file=None, env="test", llm_provider="fake")
    app = create_app(
        settings=settings,
        readiness_checks={"database": lambda: True, "redis": lambda: True},
    )
    client = TestClient(app)

    headers = {"X-API-Key": "operator-test-key-001"}
    endpoints = [
        ("GET", "/healthz", {}),
        ("GET", "/readyz", {}),
        ("GET", "/api/v1/fields", headers),
        ("GET", "/api/v1/machines", headers),
        ("GET", "/api/v1/district/ludhiana/summary", headers),
    ]

    latencies: dict[str, float] = {}
    for method, path, hdrs in endpoints:
        # Warmup
        client.get(path, headers=hdrs)

        runs = 20
        start = time.perf_counter()
        for _ in range(runs):
            client.get(path, headers=hdrs)
        avg_ms = ((time.perf_counter() - start) / runs) * 1000.0
        latencies[f"{method} {path}"] = round(avg_ms, 2)

    return latencies


def run_all_benchmarks() -> dict[str, Any]:
    """Execute complete benchmark suite and return aggregate dict."""
    print("[BENCHMARK] Running CP-SAT Scheduler Latency Benchmark...")
    sched_bench = benchmark_cpsat_scheduler()

    print("[BENCHMARK] Running EventBus In-Memory Throughput Benchmark...")
    bus_bench = benchmark_eventbus_throughput()

    print("[BENCHMARK] Running PII Redaction Pipeline Benchmark...")
    pii_bench = benchmark_pii_redaction()

    print("[BENCHMARK] Running FastAPI Endpoints Latency Benchmark...")
    api_bench = benchmark_api_endpoints()

    return {
        "scheduler_latency": sched_bench,
        "event_bus_throughput": bus_bench,
        "pii_redaction_throughput": pii_bench,
        "api_endpoint_latency_ms": api_bench,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run StubbleOS performance benchmark suite.")
    parser.add_argument("--out", "-o", default="results/benchmarks.json", help="Output JSON path")
    args = parser.parse_args()

    results = run_all_benchmarks()

    import os

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[BENCHMARK] Complete! Results saved to {args.out}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
