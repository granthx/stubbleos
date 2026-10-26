"""Schemas for Orchestrator (supervisor) agent."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.agents.buyer_demand.schemas import BuyerOrderModel, OrderBook
from stubbleos.agents.policy_guard.schemas import PolicyCheckResult
from stubbleos.core.events import Event, ReplanTriggered
from stubbleos.core.types import ApprovalStatus, PlanStatus
from stubbleos.optimization.routing import (
    BuyerDropoff,
    FieldPickup,
    TruckRoute,
    TruckSpec,
)
from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
    ScheduledAssignment,
)


class DistrictPlan(BaseModel):
    """Aggregate per-district per-day operations plan."""

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID = Field(default_factory=uuid4)
    district: str
    plan_date: date
    strategy: str
    version: int = 1
    parent_plan_id: UUID | None = None
    status: PlanStatus = PlanStatus.ACTIVE
    assignments: list[ScheduledAssignment] = Field(default_factory=list)
    routes: list[TruckRoute] = Field(default_factory=list)
    objective_value: float = 0.0
    solver_status: str = "OPTIMAL"
    confidence: float = 1.0
    explanation: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrchestratorInput(BaseModel):
    """Input payload to execute district operations planning."""

    model_config = ConfigDict(extra="forbid")

    district: str
    plan_date: date
    strategy: str = "centralized"
    jobs: list[JobRequest] = Field(default_factory=list)
    machines: list[MachineResource] = Field(default_factory=list)
    pickups: list[FieldPickup] = Field(default_factory=list)
    dropoffs: list[BuyerDropoff] = Field(default_factory=list)
    trucks: list[TruckSpec] = Field(default_factory=list)
    orders: list[BuyerOrderModel] = Field(default_factory=list)
    replan_trigger: ReplanTriggered | None = None
    previous_plan: DistrictPlan | None = None
    current_hour: float = 0.0
    confidence_threshold: float = 0.70
    force_interrupt: bool = False  # For HITL testing


class OrchestratorState(BaseModel):
    """Execution state for Orchestrator LangGraph supervisor."""

    model_config = ConfigDict(extra="forbid")

    district: str
    plan_date: date
    strategy: str
    version: int = 1
    current_hour: float = 0.0
    jobs: list[JobRequest] = Field(default_factory=list)
    machines: list[MachineResource] = Field(default_factory=list)
    pickups: list[FieldPickup] = Field(default_factory=list)
    dropoffs: list[BuyerDropoff] = Field(default_factory=list)
    trucks: list[TruckSpec] = Field(default_factory=list)
    orders: list[BuyerOrderModel] = Field(default_factory=list)
    order_book: OrderBook | None = None
    assignments: list[ScheduledAssignment] = Field(default_factory=list)
    routes: list[TruckRoute] = Field(default_factory=list)
    plan: DistrictPlan | None = None
    replan_trigger: ReplanTriggered | None = None
    previous_plan: DistrictPlan | None = None
    confidence: float = 1.0
    confidence_threshold: float = 0.70
    force_interrupt: bool = False
    policy_result: PolicyCheckResult | None = None
    approval_id: UUID | None = None
    approval_status: ApprovalStatus | None = None
    interrupt_data: dict[str, Any] | None = None
    events_to_emit: list[Event] = Field(default_factory=list)
    status: str = "initialized"
    explanation: str = ""
