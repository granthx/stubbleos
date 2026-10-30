"""Machines REST routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from stubbleos.api.auth import AuthenticatedUser, get_current_user
from stubbleos.api.schemas import MachineResponse
from stubbleos.core.types import MachineStatus, MachineType

router = APIRouter(prefix="/machines", tags=["Machines"])

MOCK_MACHINES: dict[UUID, MachineResponse] = {}


def _seed_mock_machines() -> None:
    if MOCK_MACHINES:
        return
    for i in range(1, 7):
        m_id = UUID(f"00000000-0000-0000-0001-{i:012d}")
        m_type = MachineType.SUPER_SEEDER if i % 2 == 1 else MachineType.BALER
        m_status = MachineStatus.AVAILABLE if i <= 4 else MachineStatus.IN_USE
        MOCK_MACHINES[m_id] = MachineResponse(
            id=m_id,
            machine_type=m_type,
            district="sangrur",
            status=m_status,
            current_lat=30.250 + (i * 0.015),
            current_lon=75.850 + (i * 0.012),
            capacity_acres_per_day=15.0 if m_type == MachineType.SUPER_SEEDER else 25.0,
            operator_name=f"Harpreet Singh {i}",
        )


_seed_mock_machines()


@router.get("", response_model=list[MachineResponse])
def list_machines(
    district: str = "sangrur",
    machine_type: MachineType | None = None,
    status: MachineStatus | None = None,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> list[MachineResponse]:
    _seed_mock_machines()
    items = [m for m in MOCK_MACHINES.values() if m.district.lower() == district.lower()]
    if machine_type is not None:
        items = [m for m in items if m.machine_type == machine_type]
    if status is not None:
        items = [m for m in items if m.status == status]
    return items


@router.get("/{machine_id}", response_model=MachineResponse)
def get_machine(
    machine_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> MachineResponse:
    _seed_mock_machines()
    if machine_id not in MOCK_MACHINES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
    return MOCK_MACHINES[machine_id]
