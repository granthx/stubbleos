"""Hypothesis property tests for machine scheduling and optimization invariants."""

from uuid import uuid4

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from stubbleos.core.types import LandholdingClass, MachineType
from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
    SchedulerConfig,
    solve_schedule,
)


@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    seed=st.integers(min_value=1, max_value=99999),
    num_jobs=st.integers(min_value=2, max_value=6),
    num_machines=st.integers(min_value=1, max_value=3),
)
def test_hypothesis_no_machine_double_booked_and_readiness_invariant(
    seed: int, num_jobs: int, num_machines: int
) -> None:
    # Generate test machines
    machines = [
        MachineResource(
            machine_id=uuid4(),
            machine_type=MachineType.HAPPY_SEEDER,
            capacity_acres_per_hour=1.2,
            hourly_cost_inr=1800.0,
            current_lat=30.8 + i * 0.01,
            current_lon=75.8 + i * 0.01,
            available_from_hour=0.0,
        )
        for i in range(num_machines)
    ]

    # Generate test jobs
    jobs = [
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=float(2.0 + j * 1.5),
            earliest_start_hour=float(j * 3.0),
            deadline_hour=float(25.0 + j * 5.0),
            center_lat=30.8 + j * 0.005,
            center_lon=75.8 + j * 0.005,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        )
        for j in range(num_jobs)
    ]

    cfg = SchedulerConfig(random_seed=seed, time_limit_seconds=1.0)
    out = solve_schedule(jobs=jobs, machines=machines, config=cfg)

    # 1. No machine double-booked (intervals on each machine do not overlap)
    by_machine: dict[object, list[object]] = {}
    for a in out.assignments:
        by_machine.setdefault(a.machine_id, []).append(a)

    for _m_id, m_assignments in by_machine.items():
        sorted_m = sorted(m_assignments, key=lambda x: x.start_hour)  # type: ignore[attr-defined]
        for idx in range(len(sorted_m) - 1):
            assert sorted_m[idx].end_hour <= sorted_m[idx + 1].start_hour + 1e-4  # type: ignore[attr-defined]

    # 2. No assignment starts before field readiness window
    job_map = {j.field_id: j for j in jobs}
    for a in out.assignments:
        req = job_map[a.field_id]
        assert a.start_hour >= req.earliest_start_hour - 1e-4
        if not a.is_on_time:
            assert a.end_hour > req.deadline_hour - 1e-4


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    seed=st.integers(min_value=1, max_value=99999),
)
def test_hypothesis_determinism_for_fixed_seed(seed: int) -> None:
    machines = [
        MachineResource(
            machine_id=uuid4(),
            machine_type=MachineType.SUPER_SEEDER,
            capacity_acres_per_hour=1.5,
            hourly_cost_inr=2000.0,
            current_lat=30.8,
            current_lon=75.8,
        )
    ]
    jobs = [
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.MARGINAL,
            area_acres=3.0,
            earliest_start_hour=0.0,
            deadline_hour=15.0,
            center_lat=30.81,
            center_lon=75.81,
            eligible_machine_types=[MachineType.SUPER_SEEDER],
        ),
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=20.0,
            center_lat=30.82,
            center_lon=75.82,
            eligible_machine_types=[MachineType.SUPER_SEEDER],
        ),
    ]

    cfg = SchedulerConfig(random_seed=seed, time_limit_seconds=1.0)
    out1 = solve_schedule(jobs=jobs, machines=machines, config=cfg)
    out2 = solve_schedule(jobs=jobs, machines=machines, config=cfg)

    assert len(out1.assignments) == len(out2.assignments)
    assert out1.objective_value == out2.objective_value
    for a1, a2 in zip(out1.assignments, out2.assignments, strict=True):
        assert a1.field_id == a2.field_id
        assert a1.machine_id == a2.machine_id
        assert a1.start_hour == a2.start_hour
        assert a1.end_hour == a2.end_hour
