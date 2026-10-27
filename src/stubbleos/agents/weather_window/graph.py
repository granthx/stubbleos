"""LangGraph definition for Weather & Window agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from stubbleos.agents.weather_window.logic import (
    build_replan_event,
    evaluate_weather_windows,
)
from stubbleos.agents.weather_window.schemas import WeatherWindowState
from stubbleos.core.events import EventBus

_background_tasks: set[Any] = set()


def build_weather_window_graph(
    *,
    event_bus: EventBus | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Builds and compiles the Weather & Window agent LangGraph."""

    def evaluation_node(state: WeatherWindowState) -> dict[str, Any]:
        output = evaluate_weather_windows(state.input)
        return {"output": output, "status": "evaluated"}

    def replan_check_node(state: WeatherWindowState) -> dict[str, Any]:
        if state.output is None:
            return {"status": "error_no_output"}

        replan_emitted = False
        if state.output.is_replan_triggered and event_bus is not None:
            import asyncio

            event = build_replan_event(state.output)
            if event is not None:
                try:
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(
                        event_bus.emit(event, source="weather_window", district=state.output.district)
                    )
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
                except RuntimeError:
                    asyncio.run(
                        event_bus.emit(event, source="weather_window", district=state.output.district)
                    )
                replan_emitted = True

        return {
            "replan_event_emitted": replan_emitted,
            "status": "completed",
        }

    builder = StateGraph(WeatherWindowState)
    builder.add_node("evaluation", evaluation_node)
    builder.add_node("replan_check", replan_check_node)

    builder.set_entry_point("evaluation")
    builder.add_edge("evaluation", "replan_check")
    builder.add_edge("replan_check", END)

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=cp)
