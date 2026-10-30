"""Machines REST routes."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from stubbleos.api.auth import AuthenticatedUser, get_current_user
from stubbleos.api.schemas import MachineResponse
from stubbleos.core.types import MachineStatus, MachineType

router = APIRouter(prefix="/machines", tags=["Machines"])

MOCK_MACHINES: dict[UUID, MachineResponse] = {}

DISTRICT_MACHINE_SPECS: dict[str, dict[str, Any]] = {
    "sangrur": {
        "lat": 30.250,
        "lon": 75.850,
        "operators": [
            "Harpreet Singh",
            "Gurjit Singh",
            "Balwinder Kumar",
            "Manpreet Dhillon",
            "Sukhwinder Cheema",
            "Jasvir Mann",
        ],
    },
    "patiala": {
        "lat": 30.340,
        "lon": 76.400,
        "operators": [
            "Kuldeep Walia",
            "Amrik Dhaliwal",
            "Paramjit Sandhu",
            "Jagjit Tiwana",
            "Satnam Grewal",
            "Gursewak Brar",
        ],
    },
    "ludhiana": {
        "lat": 30.880,
        "lon": 75.860,
        "operators": [
            "Davinder Gill",
            "Avtar Toor",
            "Balraj Kahlon",
            "Surjit Mangat",
            "Jarnail Deol",
            "Harnek Sekhon",
        ],
    },
    "fatehgarh": {
        "lat": 30.650,
        "lon": 76.400,
        "operators": [
            "Ranjit Bajwa",
            "Hardev Virk",
            "Bhupinder Sahi",
            "Karamjit Sidhu",
            "Charanjit Ghuman",
            "Narinder Bhatti",
        ],
    },
    "karnal": {
        "lat": 29.700,
        "lon": 76.990,
        "operators": [
            "Virender Rathi",
            "Sunil Kamboj",
            "Ramesh Dahiya",
            "Sanjay Punia",
            "Mukesh Malik",
            "Anil Jaglan",
        ],
    },
}


MACHINE_OFFSETS: list[tuple[float, float]] = [
    (-0.015, -0.012),
    (0.018, 0.015),
    (-0.022, 0.024),
    (0.025, -0.018),
    (-0.008, 0.012),
    (0.012, -0.022),
]


def _seed_mock_machines() -> None:
    if MOCK_MACHINES:
        return
    m_types = [
        MachineType.SUPER_SEEDER,
        MachineType.BALER,
        MachineType.HAPPY_SEEDER,
        MachineType.BALER,
        MachineType.SUPER_SEEDER,
        MachineType.RAKE,
    ]
    for d_counter, (dist_name, spec) in enumerate(DISTRICT_MACHINE_SPECS.items(), start=1):
        for i, op_name in enumerate(spec["operators"], start=1):
            m_id = UUID(f"200{d_counter}000{i}-0000-0000-0000-{i:012d}")
            m_type = m_types[(i - 1) % len(m_types)]
            m_status = MachineStatus.IN_USE if (i % 2 == 1) else MachineStatus.AVAILABLE
            dlat, dlon = MACHINE_OFFSETS[(i - 1) % len(MACHINE_OFFSETS)]
            lat = float(spec["lat"]) + dlat
            lon = float(spec["lon"]) + dlon
            cap = (
                15.0
                if m_type == MachineType.SUPER_SEEDER
                else (25.0 if m_type == MachineType.BALER else 12.0)
            )

            MOCK_MACHINES[m_id] = MachineResponse(
                id=m_id,
                machine_type=m_type,
                district=dist_name,
                status=m_status,
                current_lat=round(lat, 4),
                current_lon=round(lon, 4),
                capacity_acres_per_day=cap,
                operator_name=op_name,
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
