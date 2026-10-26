"""LangGraph workflow for MRV agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.mrv.logic import compute_mrv_evidence
from stubbleos.agents.mrv.schemas import MrvState


def build_mrv_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles MRV LangGraph workflow."""

    def verify_node(state: MrvState) -> dict[str, Any]:
        output = compute_mrv_evidence(state.input)
        return {"output": output, "status": "completed"}

    builder = StateGraph(MrvState)
    builder.add_node("verify", verify_node)
    builder.add_edge(START, "verify")
    builder.add_edge("verify", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
