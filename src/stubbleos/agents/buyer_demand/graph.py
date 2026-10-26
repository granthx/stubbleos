"""LangGraph workflow for Buyer Demand agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.buyer_demand.logic import build_order_book
from stubbleos.agents.buyer_demand.schemas import BuyerDemandState
from stubbleos.llm.base import LLMClient


def build_buyer_demand_graph(
    llm: LLMClient | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles the Buyer Demand LangGraph workflow."""

    async def aggregate_node(state: BuyerDemandState) -> dict[str, Any]:
        order_book = await build_order_book(state.input, llm=llm)
        return {
            "order_book": order_book,
            "status": "published",
        }

    builder = StateGraph(BuyerDemandState)
    builder.add_node("aggregate", aggregate_node)
    builder.add_edge(START, "aggregate")
    builder.add_edge("aggregate", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
