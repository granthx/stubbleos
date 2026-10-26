"""Mock tools for Weather & Window agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


@tool
def fetch_weather_forecast_mock(district: str, days: int = 7) -> dict[str, Any]:
    """Mock meteorological forecast fetching tool."""
    return {
        "district": district,
        "days": days,
        "rain_probability": 0.05,
        "max_temperature_c": 29.0,
        "wind_speed_kmh": 8.5,
    }


@tool
def check_drying_conditions_mock(district: str) -> dict[str, Any]:
    """Mock moisture and residue drying rate assessment tool."""
    return {
        "district": district,
        "drying_rate": "optimal",
        "expected_moisture_drop_per_day_pct": 2.5,
    }


def create_weather_tools() -> list[Any]:
    return [fetch_weather_forecast_mock, check_drying_conditions_mock]
