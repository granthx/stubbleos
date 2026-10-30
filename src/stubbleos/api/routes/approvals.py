"""Approvals & Human-in-the-Loop (HITL) REST routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from stubbleos.api.auth import AuthenticatedUser, Role, get_current_user, require_role
from stubbleos.api.schemas import ApprovalResolveRequest, ApprovalResponse
from stubbleos.core.types import ApprovalStatus

router = APIRouter(prefix="/approvals", tags=["Approvals"])

MOCK_APPROVALS: dict[UUID, ApprovalResponse] = {}


MOCK_APPROVALS_DATA = [
    {
        "id": UUID("00000000-0000-0004-0001-000000000001"),
        "district": "sangrur",
        "kind": "burn_threat_escalation",
        "reason": "Farmer threatening fire due to combine harvest delay in Dhuri block",
        "confidence": 0.98,
        "requested_by": "farmer_voice_agent",
    },
    {
        "id": UUID("00000000-0000-0004-0001-000000000002"),
        "district": "sangrur",
        "kind": "plan_confidence",
        "reason": "Solver confidence (0.69 < 0.75) triggered by impending 12mm rain window",
        "confidence": 0.69,
        "requested_by": "orchestrator",
    },
    {
        "id": UUID("00000000-0000-0004-0002-000000000001"),
        "district": "patiala",
        "kind": "smallholder_priority_dispute",
        "reason": "Marginal farmer in Nabha block contesting priority bump by adjacent 18-acre estate",
        "confidence": 0.88,
        "requested_by": "policy_guard",
    },
    {
        "id": UUID("00000000-0000-0004-0002-000000000002"),
        "district": "patiala",
        "kind": "moisture_anomaly",
        "reason": "Straw moisture 19% exceeds Rajpura CBG intake limit (14%); requires sun-drying window extension",
        "confidence": 0.92,
        "requested_by": "field_monitor",
    },
    {
        "id": UUID("00000000-0000-0004-0003-000000000001"),
        "district": "ludhiana",
        "kind": "machine_breakdown_reroute",
        "reason": "Super Seeder breakdown near Raikot; 4 pending smallholder fields require urgent reallocation",
        "confidence": 0.72,
        "requested_by": "machine_scheduler",
    },
    {
        "id": UUID("00000000-0000-0004-0003-000000000002"),
        "district": "ludhiana",
        "kind": "burn_threat_escalation",
        "reason": "Thermal anomaly detected near Jagraon; verified FIRMS confidence 87%",
        "confidence": 0.87,
        "requested_by": "field_monitor",
    },
    {
        "id": UUID("00000000-0000-0004-0004-000000000001"),
        "district": "fatehgarh",
        "kind": "tariff_subsidy_override",
        "reason": "Special cross-subsidy requested for women smallholder cooperative in Sirhind",
        "confidence": 0.95,
        "requested_by": "pricing_negotiation",
    },
    {
        "id": UUID("00000000-0000-0004-0005-000000000001"),
        "district": "karnal",
        "kind": "buyer_pricing_dispute",
        "reason": "Biomass pellet mill in Nilokheri offered INR 1450/t (below INR 1600/t minimum tariff floor)",
        "confidence": 0.91,
        "requested_by": "buyer_demand_agent",
    },
]


def _seed_mock_approvals() -> None:
    if MOCK_APPROVALS:
        return
    for item in MOCK_APPROVALS_DATA:
        app_id: UUID = item["id"]  # type: ignore[assignment]
        MOCK_APPROVALS[app_id] = ApprovalResponse(
            id=app_id,
            kind=str(item["kind"]),
            subject_id=uuid4(),
            district=str(item["district"]),
            reason=str(item["reason"]),
            status=ApprovalStatus.PENDING,
            confidence=float(str(item["confidence"])),
            requested_by=str(item["requested_by"]),
            created_at=datetime.now(UTC),
        )


_seed_mock_approvals()


@router.get("", response_model=list[ApprovalResponse])
def list_approvals(
    district: str | None = None,
    status: ApprovalStatus | None = None,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> list[ApprovalResponse]:
    _seed_mock_approvals()
    items = list(MOCK_APPROVALS.values())
    if district is not None:
        items = [a for a in items if a.district.lower() == district.lower()]
    if status is not None:
        items = [a for a in items if a.status == status]
    return items


@router.post("/{approval_id}/resolve", response_model=ApprovalResponse)
def resolve_approval(
    approval_id: UUID,
    req: ApprovalResolveRequest,
    user: Annotated[AuthenticatedUser, Depends(require_role({Role.ADMIN, Role.OPERATOR}))],
) -> ApprovalResponse:
    _seed_mock_approvals()
    if approval_id not in MOCK_APPROVALS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    a = MOCK_APPROVALS[approval_id]
    new_status = ApprovalStatus.APPROVED if req.decision == "approved" else ApprovalStatus.REJECTED
    resolved = a.model_copy(
        update={
            "status": new_status,
            "decided_by_role": user.role.value,
        }
    )
    MOCK_APPROVALS[approval_id] = resolved
    return resolved
