"""LangGraph workflow for Weather & Window agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.weather_window.logic import evaluate_weather_window
from stubbleos.agents.weather_window.schemas import WeatherWindowState


def build_weather_window_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles Weather Window LangGraph workflow."""

    def forecast_node(state: WeatherWindowState) -> dict[str, Any]:
        output = evaluate_weather_window(state.input)
        return {"output": output, "status": "completed"}

    builder = StateGraph(WeatherWindowState)
    builder.add_node("forecast", forecast_node)
    builder.add_edge(START, "forecast")
    builder.add_edge("forecast", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
