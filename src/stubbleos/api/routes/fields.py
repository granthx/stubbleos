"""Fields REST routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from stubbleos.api.auth import AuthenticatedUser, Role, get_current_user, require_role
from stubbleos.api.schemas import FieldRegistrationRequest, FieldResponse
from stubbleos.core.types import FieldState

router = APIRouter(prefix="/fields", tags=["Fields"])

# In-memory mock fields store for deterministic operation
MOCK_FIELDS: dict[UUID, FieldResponse] = {}


def _seed_mock_fields() -> None:
    if MOCK_FIELDS:
        return
    for i in range(1, 11):
        f_id = UUID(f"00000000-0000-0000-0000-{i:012d}")
        state = (
            FieldState.CLEARED
            if i <= 4
            else (FieldState.BURN_DETECTED if i == 5 else FieldState.HARVESTED_RESIDUE_PRESENT)
        )
        MOCK_FIELDS[f_id] = FieldResponse(
            id=f_id,
            farmer_id=uuid4(),
            district="sangrur",
            village_code=f"PB-SAN-00{i}",
            area_acres=float(2.0 + (i % 5)),
            state=state,
            state_confidence=0.92,
            burn_risk_score=0.85 if state == FieldState.HARVESTED_RESIDUE_PRESENT else 0.1,
            center_lat=30.245 + (i * 0.01),
            center_lon=75.842 + (i * 0.01),
        )


_seed_mock_fields()


@router.get("", response_model=list[FieldResponse])
def list_fields(
    district: str = "sangrur",
    state: FieldState | None = None,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> list[FieldResponse]:
    _seed_mock_fields()
    items = [f for f in MOCK_FIELDS.values() if f.district.lower() == district.lower()]
    if state is not None:
        items = [f for f in items if f.state == state]
    return items


@router.get("/{field_id}", response_model=FieldResponse)
def get_field(
    field_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> FieldResponse:
    _seed_mock_fields()
    if field_id not in MOCK_FIELDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return MOCK_FIELDS[field_id]


@router.post("", response_model=FieldResponse, status_code=status.HTTP_201_CREATED)
def register_field(
    req: FieldRegistrationRequest,
    user: Annotated[AuthenticatedUser, Depends(require_role({Role.ADMIN, Role.OPERATOR}))],
) -> FieldResponse:
    f_id = uuid4()
    field = FieldResponse(
        id=f_id,
        farmer_id=req.farmer_id,
        district=req.district,
        village_code=req.village_code,
        area_acres=req.area_acres,
        state=FieldState.NOT_HARVESTED,
        state_confidence=1.0,
        burn_risk_score=0.1,
        center_lat=req.center_lat,
        center_lon=req.center_lon,
    )
    MOCK_FIELDS[f_id] = field
    return field
