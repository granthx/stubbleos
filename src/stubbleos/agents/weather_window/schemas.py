"""Typed contracts for Weather & Window agent (Phase 4 skeleton, full in Phase 5)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class DailyForecast(BaseModel):
    """Single day meteorological forecast."""

    model_config = ConfigDict(extra="forbid")

    forecast_date: date
    rainfall_mm: float = Field(0.0, ge=0.0)
    temp_max_c: float = 30.0
    temp_min_c: float = 18.0
    humidity_pct: float = Field(45.0, ge=0.0, le=100.0)
    is_workable: bool = True


class WeatherWindowInput(BaseModel):
    """Input query to evaluate agricultural operating window."""

    model_config = ConfigDict(extra="forbid")

    district: str
    start_date: date
    end_date: date


class WeatherWindowOutput(BaseModel):
    """Evaluated weather window and field workability."""

    model_config = ConfigDict(extra="forbid")

    forecasts: list[DailyForecast]
    is_rain_predicted: bool
    workable_days_count: int
    advisory: str


class WeatherWindowState(BaseModel):
    """LangGraph state for Weather Window agent."""

    model_config = ConfigDict(extra="forbid")

    input: WeatherWindowInput
    output: WeatherWindowOutput | None = None
    status: str = "initialized"
