"""LangGraph workflow for Pricing & Negotiation agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.pricing_negotiation.logic import calculate_pricing
from stubbleos.agents.pricing_negotiation.schemas import PricingState


def build_pricing_negotiation_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles Pricing & Negotiation LangGraph workflow."""

    def price_node(state: PricingState) -> dict[str, Any]:
        output = calculate_pricing(state.input)
        return {"output": output, "status": "completed"}

    builder = StateGraph(PricingState)
    builder.add_node("price", price_node)
    builder.add_edge(START, "price")
    builder.add_edge("price", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
