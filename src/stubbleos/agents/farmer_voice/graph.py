"""LangGraph workflow for Farmer Voice agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.farmer_voice.logic import process_voice_interaction
from stubbleos.agents.farmer_voice.schemas import FarmerVoiceState
from stubbleos.llm.base import LLMClient


def build_farmer_voice_graph(
    llm: LLMClient | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles Farmer Voice LangGraph workflow."""

    async def converse_node(state: FarmerVoiceState) -> dict[str, Any]:
        output = await process_voice_interaction(state.input, llm=llm)
        return {"output": output, "status": "completed"}

    builder = StateGraph(FarmerVoiceState)
    builder.add_node("converse", converse_node)
    builder.add_edge(START, "converse")
    builder.add_edge("converse", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
