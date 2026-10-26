"""LangGraph workflow for Field Monitor agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.field_monitor.logic import detect_field_states
from stubbleos.agents.field_monitor.schemas import FieldMonitorState


def build_field_monitor_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles Field Monitor LangGraph workflow."""

    def sense_node(state: FieldMonitorState) -> dict[str, Any]:
        output = detect_field_states(state.input)
        return {"output": output, "status": "completed"}

    builder = StateGraph(FieldMonitorState)
    builder.add_node("sense", sense_node)
    builder.add_edge(START, "sense")
    builder.add_edge("sense", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
