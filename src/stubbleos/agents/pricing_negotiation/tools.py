"""Tools for Pricing & Negotiation agent."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.tools import tool

from stubbleos.agents.pricing_negotiation.logic import (
    draft_contract_terms,
    negotiate_biomass_bid,
)
from stubbleos.agents.pricing_negotiation.schemas import (
    BiomassOffer,
)


@tool
def compute_dynamic_tariff_mock(area_acres: float, landholding_class: str) -> dict[str, Any]:
    """Mock dynamic tariff computation tool."""
    return {
        "area_acres": area_acres,
        "landholding_class": landholding_class,
        "rate_per_acre_inr": 1200.0,
        "eligible_for_discount": landholding_class.lower() in {"marginal", "small"},
    }


@tool
def evaluate_buyer_bid_tool(
    buyer_id: str,
    order_id: str,
    price_per_tonne_inr: float,
    tonnes: float,
    delivery_term: str = "ex_field",
) -> dict[str, Any]:
    """Evaluates an industrial biomass purchase bid and calculates counter-offer."""
    offer = BiomassOffer(
        buyer_id=UUID(buyer_id),
        order_id=UUID(order_id),
        proposed_price_per_tonne_inr=price_per_tonne_inr,
        tonnes=tonnes,
        delivery_term="cif_plant" if delivery_term == "cif_plant" else "ex_field",
    )
    counter = negotiate_biomass_bid(offer)
    return counter.model_dump(mode="json")


@tool
def draft_contract_tool(
    field_id: str,
    farmer_id: str,
    buyer_id: str,
    price_per_tonne_inr: float,
    tonnes_agreed: float,
) -> dict[str, Any]:
    """Generates an immutable contract draft with SHA-256 integrity hash."""
    draft = draft_contract_terms(
        field_id=UUID(field_id),
        farmer_id=UUID(farmer_id),
        buyer_id=UUID(buyer_id),
        price_per_tonne_inr=price_per_tonne_inr,
        tonnes_agreed=tonnes_agreed,
    )
    return draft.model_dump(mode="json")


def create_pricing_tools() -> list[Any]:
    """Returns baseline tools for compatibility with Phase 4 tests."""
    return [compute_dynamic_tariff_mock]


def create_extended_pricing_tools() -> list[Any]:
    """Returns all pricing and negotiation tools."""
    return [
        compute_dynamic_tariff_mock,
        evaluate_buyer_bid_tool,
        draft_contract_tool,
    ]
