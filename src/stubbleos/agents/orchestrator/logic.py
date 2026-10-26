"""Pure orchestration, replanning, and conflict resolution logic."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from stubbleos.agents.orchestrator.schemas import DistrictPlan
from stubbleos.agents.policy_guard.logic import evaluate_policy
from stubbleos.agents.policy_guard.schemas import PolicyCheckRequest, PolicyCheckResult
from stubbleos.coordination.conflicts import ConflictResolver, TieBreakLog
from stubbleos.core.config import Settings
from stubbleos.core.events import ReplanTriggered
from stubbleos.core.types import (
    ApprovalStatus,
    PlanStatus,
    ReplanReason,
)
from stubbleos.data.models import Approval
from stubbleos.data.repositories import ConsentRepository
from stubbleos.optimization.routing import TruckRoute
from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
    ScheduledAssignment,
)


def calculate_plan_confidence(
    assignments: list[ScheduledAssignment],
    total_jobs: int,
    solver_status: str,
) -> float:
    """Computes a calibrated confidence score [0.0, 1.0] for the operational plan."""
    if total_jobs == 0:
        return 1.0

    if solver_status == "INFEASIBLE":
        return 0.20

    coverage_ratio = len(assignments) / max(1, total_jobs)
    on_time_ratio = (
        sum(1 for a in assignments if a.is_on_time) / max(1, len(assignments)) if assignments else 0.0
    )

    base = 0.5 * coverage_ratio + 0.4 * on_time_ratio
    if solver_status == "OPTIMAL":
        base += 0.10
    elif solver_status == "FEASIBLE":
        base += 0.05

    return round(min(1.0, max(0.0, base)), 2)


def resolve_conflicts(
    jobs: list[JobRequest],
    machine: MachineResource,
    current_hour: float,
    seed: int = 42,
) -> tuple[JobRequest, TieBreakLog]:
    """Resolves competing field claims on an idle machine resource."""
    resolver = ConflictResolver(seed=seed)
    return resolver.resolve_competition(jobs, machine, current_hour)


def handle_replan_event(
    replan_trigger: ReplanTriggered,
    jobs: list[JobRequest],
    machines: list[MachineResource],
) -> tuple[list[JobRequest], list[MachineResource]]:
    """Modifies job requests or machine resources in response to a dynamic replanning trigger."""
    reason = replan_trigger.reason
    details = replan_trigger.details

    updated_jobs = list(jobs)
    updated_machines = list(machines)

    if reason == ReplanReason.RAIN_FORECAST_CHANGE:
        # Sowing deadline is compressed due to impending rain
        compression_hours = float(details.get("deadline_compression_hours", 24.0))
        compressed_jobs = []
        for j in updated_jobs:
            new_deadline = max(j.earliest_start_hour + 1.0, j.deadline_hour - compression_hours)
            compressed_jobs.append(j.model_copy(update={"deadline_hour": new_deadline}))
        updated_jobs = compressed_jobs

    elif reason == ReplanReason.MACHINE_BREAKDOWN:
        # Machine broken down: remove from available resources
        broken_id_str = details.get("machine_id")
        if broken_id_str:
            broken_id = UUID(broken_id_str)
            updated_machines = [m for m in updated_machines if m.machine_id != broken_id]

    elif reason == ReplanReason.BURN_DETECTED:
        # Field caught fire: remove from job queue
        burnt_field_str = details.get("field_id")
        if burnt_field_str:
            burnt_id = UUID(burnt_field_str)
            updated_jobs = [j for j in updated_jobs if j.field_id != burnt_id]

    return updated_jobs, updated_machines


def create_versioned_plan(
    district: str,
    plan_date: Any,
    strategy: str,
    assignments: list[ScheduledAssignment],
    routes: list[TruckRoute],
    objective_value: float,
    solver_status: str,
    confidence: float,
    previous_plan: DistrictPlan | None = None,
    explanation: str = "",
) -> DistrictPlan:
    """Builds a new versioned DistrictPlan, linking parent plan if superseding."""
    new_version = 1
    parent_id: UUID | None = None

    if previous_plan is not None:
        new_version = previous_plan.version + 1
        parent_id = previous_plan.plan_id

    return DistrictPlan(
        plan_id=uuid4(),
        district=district,
        plan_date=plan_date,
        strategy=strategy,
        version=new_version,
        parent_plan_id=parent_id,
        status=PlanStatus.ACTIVE,
        assignments=assignments,
        routes=routes,
        objective_value=objective_value,
        solver_status=solver_status,
        confidence=confidence,
        explanation=explanation,
    )


def evaluate_plan_policy(
    plan: DistrictPlan,
    consent_repo: ConsentRepository | None = None,
    settings: Settings | None = None,
) -> PolicyCheckResult:
    """Validates outbound plan operations against the Policy Guard."""
    # Build outbound action request for the plan
    req = PolicyCheckRequest(
        action_ref=f"plan_dispatch_{plan.plan_id}",
        payload={"plan_id": str(plan.plan_id), "district": plan.district, "version": plan.version},
    )
    return evaluate_policy(req, consent_repo=consent_repo, settings=settings)


def create_approval_record(
    kind: str,
    subject_type: str,
    subject_id: UUID,
    reason: str,
    requested_by: str,
    confidence: float | None = None,
    payload: dict[str, Any] | None = None,
) -> Approval:
    """Creates an Approval domain model in PENDING status."""
    return Approval(
        id=uuid4(),
        kind=kind,
        subject_type=subject_type,
        subject_id=subject_id,
        status=ApprovalStatus.PENDING,
        reason=reason,
        confidence=confidence,
        requested_by=requested_by,
        payload=payload or {},
    )
