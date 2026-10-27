"""LangChain tools for Weather & Window agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from stubbleos.agents.weather_window.logic import (
    build_replan_event,
    evaluate_weather_window,
)
from stubbleos.agents.weather_window.schemas import (
    WeatherWindowInput,
    WeatherWindowOutput,
)
from stubbleos.core.events import EventBus


@tool
def fetch_weather_forecast_mock(district: str, days: int = 5) -> dict[str, Any]:
    """Retrieves multi-day agricultural forecast for the district."""
    return {
        "district": district,
        "days": days,
        "is_rain_predicted": False,
        "avg_temp_c": 28.5,
        "rain_mm_total": 0.0,
    }


@tool
def check_drying_conditions_mock(district: str) -> dict[str, Any]:
    """Evaluates field drying index and wind conditions for baling operations."""
    return {
        "district": district,
        "drying_index": "optimal",
        "relative_humidity_pct": 45.0,
        "wind_speed_kmh": 12.0,
        "baling_recommended": True,
    }


@tool
def evaluate_weather_windows_tool(input_dict: dict[str, Any]) -> dict[str, Any]:
    """Calculates per-field workable windows and checks for rain forecast shifts."""
    inp = WeatherWindowInput.model_validate(input_dict)
    out = evaluate_weather_window(inp)
    return out.model_dump()


@tool
async def publish_replan_event_tool(
    output_dict: dict[str, Any],
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    """Publishes a ReplanTriggered event on the bus if forecast changed beyond threshold."""
    out = WeatherWindowOutput.model_validate(output_dict)
    event = build_replan_event(out)
    if event is not None and event_bus is not None:
        await event_bus.emit(event, source="weather_window", district=out.district)
        return {"status": "replan_published", "reason": event.reason.value}
    return {"status": "none"}


def create_weather_tools(event_bus: EventBus | None = None) -> list[Any]:
    """Factory to create Weather & Window tools."""
    return [
        fetch_weather_forecast_mock,
        check_drying_conditions_mock,
    ]


create_weather_window_tools = create_weather_tools
