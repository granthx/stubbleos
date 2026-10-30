"""Bookings REST routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from stubbleos.api.auth import AuthenticatedUser, get_current_user
from stubbleos.api.schemas import BookingCreateRequest, BookingResponse
from stubbleos.core.types import BookingStatus, MachineType, ServiceType

router = APIRouter(prefix="/bookings", tags=["Bookings"])

MOCK_BOOKINGS: dict[UUID, BookingResponse] = {}


def _seed_mock_bookings() -> None:
    if MOCK_BOOKINGS:
        return
    b_id = UUID("00000000-0000-0000-0003-000000000001")
    MOCK_BOOKINGS[b_id] = BookingResponse(
        id=b_id,
        farmer_id=uuid4(),
        field_id=uuid4(),
        service_type=ServiceType.IN_SITU_SOWING,
        machine_type=MachineType.SUPER_SEEDER,
        status=BookingStatus.CONFIRMED,
        target_date="2026-11-01",
        estimated_cost_inr=3600.0,
        created_at=datetime.now(UTC),
    )


_seed_mock_bookings()


@router.get("", response_model=list[BookingResponse])
def list_bookings(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> list[BookingResponse]:
    _seed_mock_bookings()
    return list(MOCK_BOOKINGS.values())


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    req: BookingCreateRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> BookingResponse:
    b_id = uuid4()
    booking = BookingResponse(
        id=b_id,
        farmer_id=req.farmer_id,
        field_id=req.field_id,
        service_type=req.service_type,
        machine_type=req.machine_type or MachineType.SUPER_SEEDER,
        status=BookingStatus.PROPOSED,
        target_date=req.target_date,
        estimated_cost_inr=2400.0,
        created_at=datetime.now(UTC),
    )
    MOCK_BOOKINGS[b_id] = booking
    return booking


@router.post("/{booking_id}/confirm", response_model=BookingResponse)
def confirm_booking(
    booking_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> BookingResponse:
    _seed_mock_bookings()
    if booking_id not in MOCK_BOOKINGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    b = MOCK_BOOKINGS[booking_id]
    confirmed = b.model_copy(update={"status": BookingStatus.CONFIRMED})
    MOCK_BOOKINGS[booking_id] = confirmed
    return confirmed
