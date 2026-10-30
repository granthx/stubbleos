"""Fields REST routes."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from stubbleos.api.auth import AuthenticatedUser, Role, get_current_user, require_role
from stubbleos.api.schemas import FieldRegistrationRequest, FieldResponse
from stubbleos.core.types import FieldState

router = APIRouter(prefix="/fields", tags=["Fields"])

# In-memory mock fields store for deterministic operation
MOCK_FIELDS: dict[UUID, FieldResponse] = {}


DISTRICT_SPECS: dict[str, dict[str, Any]] = {
    "sangrur": {
        "prefix": "PB-SAN",
        "lat_base": 30.245,
        "lon_base": 75.842,
        "burn_idx": {5},
    },
    "patiala": {
        "prefix": "PB-PAT",
        "lat_base": 30.330,
        "lon_base": 76.390,
        "burn_idx": {4, 9},
    },
    "ludhiana": {
        "prefix": "PB-LUD",
        "lat_base": 30.880,
        "lon_base": 75.850,
        "burn_idx": {3, 8},
    },
    "fatehgarh": {
        "prefix": "PB-FGS",
        "lat_base": 30.640,
        "lon_base": 76.390,
        "burn_idx": {6},
    },
    "karnal": {
        "prefix": "HR-KAR",
        "lat_base": 29.690,
        "lon_base": 76.980,
        "burn_idx": {2, 7},
    },
}


FIELD_OFFSETS: list[tuple[float, float]] = [
    (-0.024, -0.019),
    (0.016, -0.026),
    (-0.032, 0.014),
    (0.009, 0.027),
    (0.031, -0.006),
    (-0.011, 0.036),
    (0.035, 0.021),
    (-0.027, 0.004),
    (0.019, -0.031),
    (-0.004, -0.012),
]


def _seed_mock_fields() -> None:
    if MOCK_FIELDS:
        return
    for d_counter, (dist_name, spec) in enumerate(DISTRICT_SPECS.items(), start=1):
        for i in range(1, 11):
            f_id = UUID(f"00000000-0000-0000-{d_counter:04d}-{i:012d}")
            is_burn = i in spec["burn_idx"]
            is_cleared = (i <= 4) and not is_burn
            state = (
                FieldState.BURN_DETECTED
                if is_burn
                else (FieldState.CLEARED if is_cleared else FieldState.HARVESTED_RESIDUE_PRESENT)
            )
            burn_score = (
                0.96 if is_burn else (0.82 if state == FieldState.HARVESTED_RESIDUE_PRESENT else 0.08)
            )
            dlat, dlon = FIELD_OFFSETS[(i - 1) % len(FIELD_OFFSETS)]
            lat = float(spec["lat_base"]) + dlat
            lon = float(spec["lon_base"]) + dlon

            MOCK_FIELDS[f_id] = FieldResponse(
                id=f_id,
                farmer_id=uuid4(),
                district=dist_name,
                village_code=f"{spec['prefix']}-00{i}",
                area_acres=float(2.5 + (i % 5)),
                state=state,
                state_confidence=0.94 if is_burn else 0.91,
                burn_risk_score=burn_score,
                center_lat=round(lat, 4),
                center_lon=round(lon, 4),
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
