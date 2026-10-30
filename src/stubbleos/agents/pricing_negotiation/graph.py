"""LangGraph workflow for Pricing & Negotiation agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.pricing_negotiation.logic import (
    calculate_pricing,
    draft_contract_terms,
    negotiate_biomass_bid,
)
from stubbleos.agents.pricing_negotiation.schemas import PricingState


def build_pricing_negotiation_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles Pricing & Negotiation LangGraph workflow."""

    def price_node(state: PricingState) -> dict[str, Any]:
        output = calculate_pricing(state.input)

        counter_offer = state.counter_offer
        contract_draft = state.contract_draft
        rounds = state.negotiation_rounds

        # If a biomass buyer offer is being negotiated
        if state.buyer_offer is not None:
            rounds += 1
            counter_offer = negotiate_biomass_bid(state.buyer_offer, round_number=rounds)
            if counter_offer.accepted:
                contract_draft = draft_contract_terms(
                    field_id=state.input.field_id,
                    farmer_id=state.input.farmer_id,
                    buyer_id=state.buyer_offer.buyer_id,
                    price_per_tonne_inr=counter_offer.counter_price_per_tonne_inr,
                    tonnes_agreed=state.buyer_offer.tonnes,
                    delivery_term=state.buyer_offer.delivery_term,
                    order_id=state.buyer_offer.order_id,
                )

        return {
            "output": output,
            "counter_offer": counter_offer,
            "contract_draft": contract_draft,
            "negotiation_rounds": rounds,
            "status": "completed",
        }

    builder = StateGraph(PricingState)
    builder.add_node("price", price_node)
    builder.add_edge(START, "price")
    builder.add_edge("price", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
