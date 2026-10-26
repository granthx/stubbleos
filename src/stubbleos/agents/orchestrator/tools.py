"""Tools for Orchestrator (supervisor) agent."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.tools import tool

from stubbleos.agents.orchestrator.schemas import DistrictPlan
from stubbleos.core.events import Event, EventBus, PlanCreated
from stubbleos.data.models import Approval, Plan
from stubbleos.data.repositories import ApprovalRepository, PlanRepository


def create_orchestrator_tools(
    plan_repo: PlanRepository | None = None,
    approval_repo: ApprovalRepository | None = None,
    event_bus: EventBus | None = None,
) -> list[Any]:
    """Factory to instantiate tools with repository and event bus dependencies."""

    @tool
    def persist_plan(plan_data: dict[str, Any]) -> dict[str, Any]:
        """Persists the computed DistrictPlan and supersedes previous version if present."""
        plan = DistrictPlan.model_validate(plan_data)
        if plan_repo is not None:
            # Supersede parent plan if linked
            if plan.parent_plan_id is not None:
                plan_repo.supersede(plan.parent_plan_id)

            db_plan: Plan = plan_repo.create(
                district=plan.district,
                plan_date=plan.plan_date,
                strategy=plan.strategy,
                version=plan.version,
                status=plan.status,
                parent_plan_id=plan.parent_plan_id,
                payload=plan.model_dump(mode="json"),
                objective_value=plan.objective_value,
                solver_status=plan.solver_status,
                plan_id=plan.plan_id,
            )
            return {"plan_id": str(db_plan.id), "status": "persisted"}

        return {"plan_id": str(plan.plan_id), "status": "mock_persisted"}

    @tool
    def record_approval_request(
        kind: str,
        subject_type: str,
        subject_id_str: str,
        reason: str,
        requested_by: str,
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """Registers a pending approval request for FPO coordinator review."""
        subject_id = UUID(subject_id_str)
        if approval_repo is not None:
            appr: Approval = approval_repo.create(
                kind=kind,
                subject_type=subject_type,
                subject_id=subject_id,
                reason=reason,
                requested_by=requested_by,
                confidence=confidence,
            )
            return {"approval_id": str(appr.id), "status": appr.status.value}

        return {"approval_id": "mock_approval_id", "status": "pending"}

    @tool
    async def publish_plan_created_event(
        plan_id_str: str,
        district: str,
        strategy: str,
        assigned_count: int,
        unassigned_count: int,
    ) -> dict[str, Any]:
        """Publishes typed PlanCreated event to the event bus."""
        plan_id = UUID(plan_id_str)
        if event_bus is not None:
            payload = PlanCreated(
                plan_id=plan_id,
                district=district,
                strategy=strategy,
                fields_assigned=assigned_count,
                fields_unassigned=unassigned_count,
            )
            ev: Event = await event_bus.emit(payload, source="orchestrator", district=district)
            return {"event_id": str(ev.event_id), "status": "published"}

        return {"status": "mock_published"}

    return [persist_plan, record_approval_request, publish_plan_created_event]
