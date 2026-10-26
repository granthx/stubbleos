"""Unit tests for the CP-SAT machine scheduler model."""

from uuid import uuid4

from stubbleos.core.types import LandholdingClass, MachineType
from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
    SchedulerConfig,
    solve_schedule,
)


def test_scheduler_one_job_at_a_time_no_overlap() -> None:
    m_id = uuid4()
    machine = MachineResource(
        machine_id=m_id,
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.0,
        hourly_cost_inr=1800.0,
        current_lat=30.8,
        current_lon=75.8,
        available_from_hour=0.0,
    )

    # 3 jobs of 5 acres each -> 5 hours each
    jobs = [
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=5.0,
            earliest_start_hour=0.0,
            deadline_hour=50.0,
            center_lat=30.81,
            center_lon=75.81,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=5.0,
            earliest_start_hour=0.0,
            deadline_hour=50.0,
            center_lat=30.82,
            center_lon=75.82,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=5.0,
            earliest_start_hour=0.0,
            deadline_hour=50.0,
            center_lat=30.83,
            center_lon=75.83,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
    ]

    out = solve_schedule(jobs=jobs, machines=[machine])
    assert out.solver_status in ("OPTIMAL", "FEASIBLE")
    assert len(out.assignments) == 3

    # Verify no overlaps between consecutive intervals on the same machine
    sorted_a = sorted(out.assignments, key=lambda a: a.start_hour)
    for i in range(len(sorted_a) - 1):
        assert sorted_a[i].end_hour <= sorted_a[i + 1].start_hour + 1e-4


def test_scheduler_readiness_window_constraint() -> None:
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.SUPER_SEEDER,
        capacity_acres_per_hour=1.5,
        hourly_cost_inr=2000.0,
        current_lat=30.8,
        current_lon=75.8,
        available_from_hour=0.0,
    )

    # Field only ready at hour 20.0
    job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.MEDIUM,
        area_acres=6.0,
        earliest_start_hour=20.0,
        deadline_hour=40.0,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )

    out = solve_schedule(jobs=[job], machines=[machine])
    assert len(out.assignments) == 1
    assert out.assignments[0].start_hour >= 20.0 - 1e-4


def test_scheduler_fairness_priority_under_contention() -> None:
    # 1 machine available, 2 contending jobs with same deadline and same size
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.BALER,
        capacity_acres_per_hour=2.0,
        hourly_cost_inr=2500.0,
        current_lat=30.8,
        current_lon=75.8,
        available_from_hour=0.0,
    )

    # Tight deadline where only 1 job can be served on time
    marginal_job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.MARGINAL,
        area_acres=4.0,  # 2.0 hrs
        earliest_start_hour=0.0,
        deadline_hour=2.5,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.BALER],
    )
    large_job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.LARGE,
        area_acres=4.0,  # 2.0 hrs
        earliest_start_hour=0.0,
        deadline_hour=2.5,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.BALER],
    )

    out = solve_schedule(jobs=[marginal_job, large_job], machines=[machine])
    assert len(out.assignments) >= 1
    # Marginal farmer must be selected for on-time clearance due to fairness weighting
    on_time_assignments = [a for a in out.assignments if a.is_on_time]
    assert len(on_time_assignments) == 1
    assert on_time_assignments[0].field_id == marginal_job.field_id


def test_scheduler_monotonicity_adding_machine_never_decreases_objective() -> None:
    m1 = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.0,
        hourly_cost_inr=1800.0,
        current_lat=30.8,
        current_lon=75.8,
    )
    m2 = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.0,
        hourly_cost_inr=1800.0,
        current_lat=30.81,
        current_lon=75.81,
    )

    jobs = [
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=10.0,
            center_lat=30.8,
            center_lon=75.8,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=10.0,
            center_lat=30.81,
            center_lon=75.81,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
    ]

    out_1 = solve_schedule(jobs=jobs, machines=[m1])
    out_2 = solve_schedule(jobs=jobs, machines=[m1, m2])

    assert out_2.objective_value >= out_1.objective_value - 1e-4
    assert len(out_2.assignments) >= len(out_1.assignments)


def test_scheduler_time_limit_greedy_fallback() -> None:
    # A tiny time limit (0.001s) forces timeout fallback
    cfg = SchedulerConfig(time_limit_seconds=0.0001)
    m = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.SUPER_SEEDER,
        capacity_acres_per_hour=1.5,
        hourly_cost_inr=2000.0,
        current_lat=30.8,
        current_lon=75.8,
    )
    job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SMALL,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )

    out = solve_schedule(jobs=[job], machines=[m], config=cfg)
    assert out.solver_status in ("OPTIMAL", "FEASIBLE", "FALLBACK_GREEDY")
    assert len(out.assignments) == 1
    assert out.assignments[0].field_id == job.field_id
