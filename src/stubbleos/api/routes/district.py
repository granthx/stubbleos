"""District Command Center overview REST routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from stubbleos.api.auth import AuthenticatedUser, get_current_user
from stubbleos.api.routes.approvals import MOCK_APPROVALS
from stubbleos.api.routes.contracts import MOCK_CONTRACTS
from stubbleos.api.routes.fields import MOCK_FIELDS
from stubbleos.api.routes.machines import MOCK_MACHINES
from stubbleos.api.schemas import DistrictSummaryResponse
from stubbleos.core.types import ApprovalStatus, ContractStatus, FieldState, MachineStatus

router = APIRouter(prefix="/district-summary", tags=["District"])


@router.get("/{district}", response_model=DistrictSummaryResponse)
def get_district_summary(
    district: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> DistrictSummaryResponse:
    dist_lower = district.lower()

    fields = [f for f in MOCK_FIELDS.values() if f.district.lower() == dist_lower]
    machines = [m for m in MOCK_MACHINES.values() if m.district.lower() == dist_lower]

    total_fields = len(fields)
    cleared = sum(1 for f in fields if f.state == FieldState.CLEARED)
    residue = sum(1 for f in fields if f.state == FieldState.HARVESTED_RESIDUE_PRESENT)
    burns = sum(1 for f in fields if f.state == FieldState.BURN_DETECTED)

    cleared_acres = sum(f.area_acres for f in fields if f.state == FieldState.CLEARED)
    avoided_co2e = cleared_acres * 1.8  # ~1.8 tonnes CO2e avoided per acre

    active_machines = sum(1 for m in machines if m.status in {MachineStatus.IN_USE, MachineStatus.AVAILABLE})
    pending_approvals = sum(1 for a in MOCK_APPROVALS.values() if a.status == ApprovalStatus.PENDING)
    open_orders = sum(1 for c in MOCK_CONTRACTS.values() if c.status != ContractStatus.CANCELLED)

    burn_risk_idx = round(residue / max(1, total_fields), 2)

    return DistrictSummaryResponse(
        district=district,
        total_fields=total_fields,
        cleared_fields=cleared,
        pending_residue_fields=residue,
        burn_incidents_detected=burns,
        burn_risk_index=burn_risk_idx,
        active_machines_count=active_machines,
        total_stubble_cleared_acres=round(cleared_acres, 1),
        indicative_co2e_avoided_tonnes=round(avoided_co2e, 1),
        pending_approvals_count=pending_approvals,
        open_biomass_orders_count=open_orders,
    )
