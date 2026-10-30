"""Plans and Re-planning REST routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from stubbleos.api.auth import AuthenticatedUser, Role, get_current_user, require_role
from stubbleos.api.schemas import PlanSummaryResponse, ReplanTriggerRequest
from stubbleos.core.types import PlanStatus

router = APIRouter(prefix="/plans", tags=["Plans"])

MOCK_PLANS: dict[UUID, PlanSummaryResponse] = {}


def _seed_mock_plans() -> None:
    if MOCK_PLANS:
        return
    p_id = UUID("00000000-0000-0000-0002-000000000001")
    MOCK_PLANS[p_id] = PlanSummaryResponse(
        id=p_id,
        district="sangrur",
        plan_date="2026-11-01",
        strategy="stubbleos_centralized_cpsat",
        status=PlanStatus.ACTIVE,
        fields_assigned=18,
        fields_unassigned=2,
        confidence=0.91,
        routes_count=5,
    )


_seed_mock_plans()


@router.get("", response_model=list[PlanSummaryResponse])
def list_plans(
    district: str = "sangrur",
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> list[PlanSummaryResponse]:
    _seed_mock_plans()
    return [p for p in MOCK_PLANS.values() if p.district.lower() == district.lower()]


@router.get("/{plan_id}", response_model=PlanSummaryResponse)
def get_plan(
    plan_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> PlanSummaryResponse:
    _seed_mock_plans()
    if plan_id not in MOCK_PLANS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return MOCK_PLANS[plan_id]


@router.post("/replan", response_model=PlanSummaryResponse)
def trigger_replan(
    req: ReplanTriggerRequest,
    user: Annotated[AuthenticatedUser, Depends(require_role({Role.ADMIN, Role.OPERATOR}))],
) -> PlanSummaryResponse:
    p_id = uuid4()
    plan = PlanSummaryResponse(
        id=p_id,
        district=req.district,
        plan_date="2026-11-02",
        strategy="emergency_replan_cpsat" if req.emergency else "adaptive_replan_cpsat",
        status=PlanStatus.DRAFT,
        fields_assigned=20,
        fields_unassigned=0,
        confidence=0.94,
        routes_count=6,
    )
    MOCK_PLANS[p_id] = plan
    return plan
