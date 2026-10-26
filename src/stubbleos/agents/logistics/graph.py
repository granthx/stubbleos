"""LangGraph workflow for Logistics agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.logistics.logic import run_logistics
from stubbleos.agents.logistics.schemas import LogisticsState
from stubbleos.llm.base import LLMClient


def build_logistics_graph(
    llm: LLMClient | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles the Logistics LangGraph workflow."""

    async def solve_node(state: LogisticsState) -> dict[str, Any]:
        output = await run_logistics(state.input, llm=llm)
        return {
            "output": output,
            "routes": output.routes,
            "explanation": output.explanation,
            "status": "completed",
        }

    builder = StateGraph(LogisticsState)
    builder.add_node("solve", solve_node)
    builder.add_edge(START, "solve")
    builder.add_edge("solve", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
