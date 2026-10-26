"""LangGraph supervisor workflow for Orchestrator."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from stubbleos.agents.buyer_demand.logic import build_order_book
from stubbleos.agents.buyer_demand.schemas import BuyerDemandInput
from stubbleos.agents.logistics.logic import run_logistics
from stubbleos.agents.logistics.schemas import LogisticsInput
from stubbleos.agents.machine_scheduler.logic import run_machine_scheduler
from stubbleos.agents.machine_scheduler.schemas import MachineSchedulerInput
from stubbleos.agents.orchestrator.logic import (
    calculate_plan_confidence,
    create_versioned_plan,
    handle_replan_event,
)
from stubbleos.agents.orchestrator.schemas import OrchestratorState
from stubbleos.agents.policy_guard.logic import evaluate_policy
from stubbleos.agents.policy_guard.schemas import PolicyCheckRequest
from stubbleos.core.clock import IST
from stubbleos.core.config import Settings
from stubbleos.core.events import ApprovalRequested, ApprovalResolved, EventBus, PlanCreated
from stubbleos.core.types import ApprovalStatus, PlanStatus
from stubbleos.data.repositories import ApprovalRepository, ConsentRepository, PlanRepository
from stubbleos.llm.base import LLMClient
from stubbleos.optimization.routing import RoutingConfig
from stubbleos.optimization.scheduler import SchedulerConfig


def build_orchestrator_graph(
    llm: LLMClient | None = None,
    plan_repo: PlanRepository | None = None,
    approval_repo: ApprovalRepository | None = None,
    consent_repo: ConsentRepository | None = None,
    event_bus: EventBus | None = None,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles the Orchestrator supervisor LangGraph workflow."""

    async def intake_node(state: OrchestratorState) -> dict[str, Any]:
        """Routes work and handles replan events (rain, breakdowns, fires)."""
        jobs = list(state.jobs)
        machines = list(state.machines)

        if state.replan_trigger is not None:
            jobs, machines = handle_replan_event(state.replan_trigger, jobs, machines)

        # Aggregate buyer demand if orders present
        order_book = None
        if state.orders:
            demand_input = BuyerDemandInput(
                district=state.district,
                target_date=state.plan_date,
                orders=state.orders,
                request_explanation=False,
            )
            order_book = await build_order_book(demand_input, llm=llm)

        return {
            "jobs": jobs,
            "machines": machines,
            "order_book": order_book,
            "status": "intake_completed",
        }

    async def schedule_node(state: OrchestratorState) -> dict[str, Any]:
        """Dispatches job requests to machine scheduler agent."""
        mode = "auction" if "decentralized" in state.strategy.lower() else "cpsat"
        sched_input = MachineSchedulerInput(
            jobs=state.jobs,
            machines=state.machines,
            mode=mode,
            config=SchedulerConfig(time_limit_seconds=0.1),
            current_hour=state.current_hour,
            request_explanation=False,
        )
        sched_output = await run_machine_scheduler(sched_input, llm=llm)
        return {
            "assignments": sched_output.assignments,
            "explanation": sched_output.explanation,
            "status": "scheduling_completed",
        }

    async def logistics_node(state: OrchestratorState) -> dict[str, Any]:
        """Dispatches transport nodes to logistics agent if trucks and pickups exist."""
        routes: list[Any] = []
        if state.pickups and state.trucks:
            log_input = LogisticsInput(
                pickups=state.pickups,
                dropoffs=state.dropoffs,
                trucks=state.trucks,
                config=RoutingConfig(time_limit_seconds=0.1),
                request_explanation=False,
            )
            log_output = await run_logistics(log_input, llm=llm)
            routes = log_output.routes

        return {
            "routes": routes,
            "status": "logistics_completed",
        }

    async def policy_and_confidence_node(state: OrchestratorState) -> dict[str, Any]:
        """Evaluates plan confidence and verifies compliance with Policy Guard."""
        confidence = calculate_plan_confidence(
            assignments=state.assignments,
            total_jobs=len(state.jobs),
            solver_status="OPTIMAL" if state.assignments or not state.jobs else "FEASIBLE",
        )

        # Validate outbound plan action (scheduled for operational hours on plan_date)
        op_time = datetime.combine(state.plan_date, datetime.min.time().replace(hour=10), tzinfo=IST)
        policy_req = PolicyCheckRequest(
            action_ref=f"plan_dispatch_{state.district}_{state.plan_date}",
            timestamp=op_time,
            payload={"district": state.district, "assigned_count": len(state.assignments)},
        )
        policy_res = evaluate_policy(policy_req, consent_repo=consent_repo, settings=settings)

        needs_approval = (
            confidence < state.confidence_threshold
            or (policy_res is not None and not policy_res.is_allowed)
            or state.force_interrupt
        )
        approval_id: UUID | None = None
        if needs_approval:
            approval_id = uuid4()
            reason = (
                f"Low confidence ({confidence:.2f} < {state.confidence_threshold:.2f})"
                if confidence < state.confidence_threshold
                else "Policy violation detected on plan dispatch"
            )
            if approval_repo is not None:
                approval_repo.create(
                    kind="plan_confidence" if confidence < state.confidence_threshold else "policy_violation",
                    subject_type="plan",
                    subject_id=approval_id,
                    reason=reason,
                    requested_by="orchestrator",
                    confidence=confidence,
                    approval_id=approval_id,
                )
            if event_bus is not None:
                await event_bus.emit(
                    ApprovalRequested(
                        approval_id=approval_id,
                        kind="plan_confidence",
                        subject_id=approval_id,
                        reason=reason,
                        confidence=confidence,
                    ),
                    source="orchestrator",
                    district=state.district,
                )

        return {
            "confidence": confidence,
            "policy_result": policy_res,
            "approval_id": approval_id,
            "status": "evaluated",
        }

    async def approval_gate_node(state: OrchestratorState) -> dict[str, Any]:
        """Human-in-the-loop approval gate using LangGraph interrupt."""
        if state.approval_id is None:
            return {"approval_status": ApprovalStatus.APPROVED, "status": "approved"}

        # Pause graph execution via LangGraph interrupt
        resume_val: Any = interrupt(
            {
                "approval_id": str(state.approval_id),
                "confidence": state.confidence,
            }
        )

        # Process resume payload
        is_approved = False
        decided_role = "fpo_coordinator"
        if isinstance(resume_val, dict):
            status_val = resume_val.get("status")
            is_approved = status_val == "approved" or resume_val.get("approved") is True
            decided_role = resume_val.get("decided_by_role", "fpo_coordinator")

        resolved_status = ApprovalStatus.APPROVED if is_approved else ApprovalStatus.REJECTED

        if approval_repo is not None:
            approval_repo.resolve(
                approval_id=state.approval_id,
                status=resolved_status,
                decided_by_role=decided_role,
            )

        if event_bus is not None:
            await event_bus.emit(
                ApprovalResolved(
                    approval_id=state.approval_id,
                    status=resolved_status,
                    decided_by_role=decided_role,
                ),
                source="orchestrator",
                district=state.district,
            )

        return {
            "approval_status": resolved_status,
            "status": "approved" if is_approved else "rejected",
        }

    async def persist_node(state: OrchestratorState) -> dict[str, Any]:
        """Creates versioned plan, supersedes parent plan if replanned, and persists."""
        if state.approval_status == ApprovalStatus.REJECTED:
            return {"status": "aborted_rejected"}

        objective_val = sum(100.0 for a in state.assignments if a.is_on_time)
        plan = create_versioned_plan(
            district=state.district,
            plan_date=state.plan_date,
            strategy=state.strategy,
            assignments=state.assignments,
            routes=state.routes,
            objective_value=objective_val,
            solver_status="OPTIMAL" if state.assignments or not state.jobs else "FEASIBLE",
            confidence=state.confidence,
            previous_plan=state.previous_plan,
            explanation=state.explanation,
        )

        # Persist to database repository
        if plan_repo is not None:
            if plan.parent_plan_id is not None:
                plan_repo.supersede(plan.parent_plan_id)

            plan_repo.create(
                district=plan.district,
                plan_date=plan.plan_date,
                strategy=plan.strategy,
                version=plan.version,
                status=PlanStatus.ACTIVE,
                parent_plan_id=plan.parent_plan_id,
                payload=plan.model_dump(mode="json"),
                objective_value=plan.objective_value,
                solver_status=plan.solver_status,
                plan_id=plan.plan_id,
            )

        # Publish PlanCreated event
        if event_bus is not None:
            await event_bus.emit(
                PlanCreated(
                    plan_id=plan.plan_id,
                    district=plan.district,
                    strategy=plan.strategy,
                    fields_assigned=len(plan.assignments),
                    fields_unassigned=len(state.jobs) - len(plan.assignments),
                ),
                source="orchestrator",
                district=plan.district,
            )

        return {
            "plan": plan,
            "status": "completed",
        }

    builder = StateGraph(OrchestratorState)
    builder.add_node("intake", intake_node)
    builder.add_node("schedule", schedule_node)
    builder.add_node("logistics", logistics_node)
    builder.add_node("policy_and_confidence", policy_and_confidence_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("persist", persist_node)

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "schedule")
    builder.add_edge("schedule", "logistics")
    builder.add_edge("logistics", "policy_and_confidence")
    builder.add_edge("policy_and_confidence", "approval_gate")

    # Conditional branching: if rejected, route to END; if approved, route to persist
    def route_after_approval(s: OrchestratorState) -> str:
        if s.approval_status == ApprovalStatus.REJECTED:
            return END
        return "persist"

    builder.add_conditional_edges("approval_gate", route_after_approval, {"persist": "persist", END: END})
    builder.add_edge("persist", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
