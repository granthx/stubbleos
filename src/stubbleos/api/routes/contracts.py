"""Contracts and Biomass Marketplace REST routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from stubbleos.agents.pricing_negotiation.logic import (
    draft_contract_terms,
    negotiate_biomass_bid,
)
from stubbleos.agents.pricing_negotiation.schemas import BiomassOffer
from stubbleos.api.auth import AuthenticatedUser, Role, get_current_user, require_role
from stubbleos.api.schemas import BiomassBidRequest, ContractResponse
from stubbleos.core.types import ContractStatus

router = APIRouter(prefix="/contracts", tags=["Contracts"])

MOCK_CONTRACTS: dict[UUID, ContractResponse] = {}


def _seed_mock_contracts() -> None:
    if MOCK_CONTRACTS:
        return
    c_id = UUID("00000000-0000-0000-0005-000000000001")
    MOCK_CONTRACTS[c_id] = ContractResponse(
        id=c_id,
        farmer_id=uuid4(),
        field_id=uuid4(),
        buyer_id=uuid4(),
        price_inr_per_tonne=1700.0,
        tonnes_agreed=100.0,
        status=ContractStatus.ACCEPTED,
        contract_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        terms={"delivery_term": "ex_field", "moisture_max_pct": 14.0},
        created_at=datetime.now(UTC),
    )


_seed_mock_contracts()


@router.get("", response_model=list[ContractResponse])
def list_contracts(
    status: ContractStatus | None = None,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> list[ContractResponse]:
    _seed_mock_contracts()
    items = list(MOCK_CONTRACTS.values())
    if status is not None:
        items = [c for c in items if c.status == status]
    return items


@router.post("/negotiate")
def negotiate_bid(
    req: BiomassBidRequest,
    user: Annotated[AuthenticatedUser, Depends(require_role({Role.ADMIN, Role.BUYER, Role.OPERATOR}))],
) -> dict[str, Any]:
    """Evaluates industrial buyer bid and returns acceptance or counter-offer."""
    offer = BiomassOffer(
        buyer_id=req.buyer_id,
        order_id=req.order_id,
        proposed_price_per_tonne_inr=req.price_per_tonne_inr,
        tonnes=req.tonnes,
        delivery_term=req.delivery_term,
        moisture_max_pct=req.moisture_max_pct,
    )
    counter = negotiate_biomass_bid(offer)

    contract = None
    if counter.accepted:
        # Create draft contract
        fld_id = uuid4()
        frm_id = uuid4()
        draft = draft_contract_terms(
            field_id=fld_id,
            farmer_id=frm_id,
            buyer_id=req.buyer_id,
            price_per_tonne_inr=req.price_per_tonne_inr,
            tonnes_agreed=req.tonnes,
            delivery_term=req.delivery_term,
            order_id=req.order_id,
        )
        c_resp = ContractResponse(
            id=draft.contract_id,
            farmer_id=frm_id,
            field_id=fld_id,
            buyer_id=req.buyer_id,
            price_inr_per_tonne=draft.price_per_tonne_inr,
            tonnes_agreed=draft.tonnes_agreed,
            status=ContractStatus.DRAFT,
            contract_sha256=draft.contract_sha256,
            terms={"delivery_term": draft.delivery_term},
            created_at=datetime.now(UTC),
        )
        MOCK_CONTRACTS[draft.contract_id] = c_resp
        contract = c_resp.model_dump(mode="json")

    return {
        "counter_offer": counter.model_dump(mode="json"),
        "contract": contract,
    }


@router.post("/{contract_id}/accept", response_model=ContractResponse)
def accept_contract(
    contract_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(require_role({Role.ADMIN, Role.OPERATOR, Role.BUYER}))],
) -> ContractResponse:
    _seed_mock_contracts()
    if contract_id not in MOCK_CONTRACTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    c = MOCK_CONTRACTS[contract_id]
    accepted = c.model_copy(update={"status": ContractStatus.ACCEPTED})
    MOCK_CONTRACTS[contract_id] = accepted
    return accepted
