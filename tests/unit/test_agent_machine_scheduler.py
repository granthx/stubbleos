"""Unit and invariant tests for Machine Scheduler agent."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from stubbleos.agents.machine_scheduler.graph import build_machine_scheduler_graph
from stubbleos.agents.machine_scheduler.logic import run_machine_scheduler
from stubbleos.agents.machine_scheduler.schemas import (
    MachineSchedulerInput,
    MachineSchedulerState,
)
from stubbleos.core.types import LandholdingClass, MachineType
from stubbleos.llm.fake import FakeLLM
from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
    SchedulerConfig,
)


@pytest.fixture
def sample_jobs_and_machines() -> tuple[list[JobRequest], list[MachineResource]]:
    jobs = [
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=48.0,
            center_lat=30.25,
            center_lon=75.80,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.MARGINAL,
            area_acres=2.5,
            earliest_start_hour=0.0,
            deadline_hour=36.0,
            center_lat=30.26,
            center_lon=75.82,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
    ]
    machines = [
        MachineResource(
            machine_id=uuid.uuid4(),
            machine_type=MachineType.HAPPY_SEEDER,
            capacity_acres_per_hour=1.5,
            hourly_cost_inr=800.0,
            current_lat=30.24,
            current_lon=75.79,
            available_from_hour=0.0,
        )
    ]
    return jobs, machines


@pytest.mark.asyncio
async def test_machine_scheduler_cpsat(
    sample_jobs_and_machines: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    jobs, machines = sample_jobs_and_machines
    fake_llm = FakeLLM(default="CP-SAT prioritised marginal smallholder with tight deadline.")

    input_data = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="cpsat",
        config=SchedulerConfig(time_limit_seconds=0.2),
        request_explanation=True,
    )

    output = await run_machine_scheduler(input_data, llm=fake_llm)

    assert len(output.assignments) > 0
    assert output.solver_status in {"OPTIMAL", "FEASIBLE"}
    assert "CP-SAT prioritised" in output.explanation
    assert output.mode_used == "cpsat"


@pytest.mark.asyncio
async def test_machine_scheduler_auction(
    sample_jobs_and_machines: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    jobs, machines = sample_jobs_and_machines
    fake_llm = FakeLLM(default="Contract-Net auction awarded task to closest idle machine.")

    input_data = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="auction",
        current_hour=0.0,
        request_explanation=True,
    )

    output = await run_machine_scheduler(input_data, llm=fake_llm)

    assert len(output.assignments) > 0
    assert output.mode_used == "auction"
    assert "Contract-Net auction" in output.explanation
    assert len(output.audit_logs) > 0


@pytest.mark.asyncio
async def test_llm_invariant_does_not_alter_assignments(
    sample_jobs_and_machines: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    """CRITICAL TEST: Ensure LLM outputs cannot mutate the optimizer assignment list."""
    jobs, machines = sample_jobs_and_machines

    # Malicious fake LLM attempting to claim different assignments or inject hallucinated fields
    fake_llm = FakeLLM(default='{"hallucinated_assignment": "reassign_all_fields_to_bogus_machine"}')

    input_data = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="cpsat",
        request_explanation=True,
    )

    output = await run_machine_scheduler(input_data, llm=fake_llm)

    # Validates that all assignments belong only to valid input fields and machines
    valid_field_ids = {j.field_id for j in jobs}
    valid_machine_ids = {m.machine_id for m in machines}

    for a in output.assignments:
        assert a.field_id in valid_field_ids
        assert a.machine_id in valid_machine_ids


@pytest.mark.asyncio
async def test_machine_scheduler_graph(
    sample_jobs_and_machines: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    jobs, machines = sample_jobs_and_machines
    fake_llm = FakeLLM(default="Graph allocation completed.")

    graph = build_machine_scheduler_graph(llm=fake_llm)

    input_data = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="cpsat",
        request_explanation=True,
    )
    state = MachineSchedulerState(input=input_data)
    res = await graph.ainvoke(state, config={"configurable": {"thread_id": "ms_test"}})

    assert res["status"] == "completed"
    assert len(res["assignments"]) > 0


def test_machine_scheduler_failure_mode_bad_data() -> None:
    """Failure-mode test: Malformed input data is rejected by Pydantic."""
    with pytest.raises(ValidationError):
        MachineSchedulerInput(
            jobs=[],
            machines=[],
            mode="unsupported_quantum_mode",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_machine_scheduler_failure_mode_infeasible_empty() -> None:
    """Failure-mode test: Empty machinery fleet returns zero assignments safely."""
    job = JobRequest(
        field_id=uuid.uuid4(),
        farmer_id=uuid.uuid4(),
        landholding_class=LandholdingClass.SMALL,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=24.0,
        center_lat=30.0,
        center_lon=75.0,
        eligible_machine_types=[MachineType.HAPPY_SEEDER],
    )
    input_data = MachineSchedulerInput(
        jobs=[job],
        machines=[],  # No machines available!
        mode="cpsat",
        request_explanation=False,
    )

    output = await run_machine_scheduler(input_data)
    assert len(output.assignments) == 0
    assert job.field_id in output.unassigned_job_ids
