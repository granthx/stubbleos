"""Logic and mock forecasting for Weather & Window agent."""

from __future__ import annotations

from datetime import timedelta

from stubbleos.agents.weather_window.schemas import (
    DailyForecast,
    WeatherWindowInput,
    WeatherWindowOutput,
)


def evaluate_weather_window(input_data: WeatherWindowInput) -> WeatherWindowOutput:
    """Evaluates multi-day meteorological window for field operations."""
    current = input_data.start_date
    forecasts: list[DailyForecast] = []
    has_rain = False
    workable_count = 0

    while current <= input_data.end_date:
        # Dry sunny autumn day default in northwest India
        fc = DailyForecast(
            forecast_date=current,
            rainfall_mm=0.0,
            temp_max_c=28.5,
            temp_min_c=16.0,
            humidity_pct=42.0,
            is_workable=True,
        )
        forecasts.append(fc)
        workable_count += 1
        current += timedelta(days=1)

    advisory = "Clear skies predicted. Favorable conditions for in-situ seeding and baling."
    return WeatherWindowOutput(
        forecasts=forecasts,
        is_rain_predicted=has_rain,
        workable_days_count=workable_count,
        advisory=advisory,
    )
