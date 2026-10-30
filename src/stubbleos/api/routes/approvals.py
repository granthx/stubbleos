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


def _seed_mock_approvals() -> None:
    if MOCK_APPROVALS:
        return
    a_id = UUID("00000000-0000-0000-0004-000000000001")
    MOCK_APPROVALS[a_id] = ApprovalResponse(
        id=a_id,
        kind="plan_confidence",
        subject_id=uuid4(),
        reason="Low solver confidence score (0.68 < 0.75 threshold) due to rain window shift",
        status=ApprovalStatus.PENDING,
        confidence=0.68,
        requested_by="orchestrator",
        created_at=datetime.now(UTC),
    )


_seed_mock_approvals()


@router.get("", response_model=list[ApprovalResponse])
def list_approvals(
    status: ApprovalStatus | None = None,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> list[ApprovalResponse]:
    _seed_mock_approvals()
    items = list(MOCK_APPROVALS.values())
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
