"""Pure scheduling and explanation logic for Machine Scheduler agent."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from stubbleos.agents.machine_scheduler.schemas import (
    MachineSchedulerInput,
    MachineSchedulerOutput,
)
from stubbleos.coordination.auction import ContractNetCoordinator, TaskAnnouncement
from stubbleos.llm.base import LLMClient, LLMRequest
from stubbleos.optimization.scheduler import ScheduledAssignment, solve_schedule


async def generate_schedule_explanation(
    assignments: list[ScheduledAssignment],
    unassigned_ids: list[UUID],
    objective_value: float,
    mode: str,
    llm: LLMClient | None = None,
) -> str:
    """Generate an auditable, natural-language explanation of scheduling results.

    INVARIANT: The LLM only explains the results and NEVER alters assignments.
    """
    total = len(assignments) + len(unassigned_ids)
    on_time = sum(1 for a in assignments if a.is_on_time)
    fallback_summary = (
        f"Scheduled {len(assignments)}/{total} fields using {mode.upper()}. "
        f"On-time completions: {on_time}/{len(assignments)}. "
        f"Objective score: {objective_value:.1f}. "
        f"{len(unassigned_ids)} fields remain pending next available machinery."
    )

    if llm is None:
        return fallback_summary

    prompt = (
        f"You are the StubbleOS Machine Scheduler coordinator. Explain this allocation decision concisely to field operators:\n"
        f"- Allocation Mode: {mode.upper()}\n"
        f"- Assigned Fields: {len(assignments)}\n"
        f"- Pending Unassigned Fields: {len(unassigned_ids)}\n"
        f"- On-time Deliveries: {on_time}\n"
        f"- Optimization Objective Score: {objective_value:.1f}\n"
        f"Summarize the rationale focusing on smallholder fairness, deadline urgency, and transit efficiency. Do not alter assignments."
    )
    try:
        response = await llm.generate(
            LLMRequest.simple(user_text=prompt, purpose="scheduler_explanation", max_tokens=256)
        )
        return response.text.strip()
    except Exception:
        return fallback_summary


async def run_machine_scheduler(
    input_data: MachineSchedulerInput,
    llm: LLMClient | None = None,
) -> MachineSchedulerOutput:
    """Runs the machine scheduler in either CP-SAT global optimization or Contract-Net auction mode."""
    t0 = time.perf_counter()

    if input_data.mode == "cpsat":
        cpsat_res = solve_schedule(
            jobs=input_data.jobs,
            machines=input_data.machines,
            config=input_data.config,
        )
        assignments = list(cpsat_res.assignments)
        unassigned_ids = list(cpsat_res.unassigned_field_ids)
        objective_value = cpsat_res.objective_value
        solver_status = cpsat_res.solver_status
        audit_logs: list[dict[str, Any]] = []

    elif input_data.mode == "auction":
        coordinator = ContractNetCoordinator(seed=input_data.seed)
        tasks = [
            TaskAnnouncement(
                task_id=j.field_id,
                farmer_id=j.farmer_id,
                landholding_class=j.landholding_class,
                area_acres=j.area_acres,
                center_lat=j.center_lat,
                center_lon=j.center_lon,
                earliest_start_hour=j.earliest_start_hour,
                deadline_hour=j.deadline_hour,
                eligible_machine_types=j.eligible_machine_types,
            )
            for j in input_data.jobs
        ]
        auction_res = coordinator.run_auction_round(
            tasks=tasks,
            machines=input_data.machines,
            current_hour=input_data.current_hour,
        )

        assignments = [
            ScheduledAssignment(
                field_id=award.task_id,
                machine_id=award.machine_id,
                start_hour=award.scheduled_start_hour,
                duration_hours=round(award.scheduled_completion_hour - award.scheduled_start_hour, 2),
                end_hour=award.scheduled_completion_hour,
                transit_hours=0.0,
                transit_distance_km=0.0,
                is_on_time=award.is_on_time,
            )
            for award in auction_res.awards
        ]
        unassigned_ids = list(auction_res.unawarded_task_ids)
        # Utility objective: 1000 for on time, -500 for late
        objective_value = sum(1000.0 if a.is_on_time else -500.0 for a in assignments)
        solver_status = "OPTIMAL" if not unassigned_ids else "FEASIBLE"
        audit_logs = [
            award.tie_break_log.model_dump()
            for award in auction_res.awards
            if award.tie_break_log is not None
        ]
    else:
        raise ValueError(f"Unsupported scheduling mode: {input_data.mode}")

    wall_time = time.perf_counter() - t0

    explanation = ""
    if input_data.request_explanation:
        explanation = await generate_schedule_explanation(
            assignments=assignments,
            unassigned_ids=unassigned_ids,
            objective_value=objective_value,
            mode=input_data.mode,
            llm=llm,
        )

    return MachineSchedulerOutput(
        assignments=assignments,
        unassigned_job_ids=unassigned_ids,
        objective_value=round(objective_value, 2),
        solver_status=solver_status,
        wall_time_seconds=round(wall_time, 4),
        explanation=explanation,
        audit_logs=audit_logs,
        mode_used=input_data.mode,
    )
