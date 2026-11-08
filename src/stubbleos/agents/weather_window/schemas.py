"""Schemas for Weather & Window agent and weather evaluation."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DailyForecast(BaseModel):
    """Single day meteorological forecast with workability evaluation."""

    model_config = ConfigDict(extra="forbid")

    forecast_date: date
    precipitation_mm: float = Field(0.0, ge=0.0)
    wind_speed_max_kmh: float = Field(10.0, ge=0.0)
    temp_max_c: float = 30.0
    temp_min_c: float = 18.0
    humidity_mean_pct: float = Field(50.0, ge=0.0, le=100.0)
    soil_moisture_index: float = Field(0.20, ge=0.0, le=1.0)
    is_workable: bool = True


DailyWeatherForecast = DailyForecast


class FieldOperatingWindow(BaseModel):
    """Per-field operating window analysis up to the wheat sowing deadline."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    sowing_deadline: date
    days_remaining_to_deadline: int
    total_workable_days: int
    safe_operating_windows: list[tuple[date, date]] = Field(default_factory=list)
    urgency_level: str = "medium"  # low | medium | high | critical
    advisory: str


class WeatherWindowInput(BaseModel):
    """Input query to compute safe operating windows and check for forecast shifts."""

    model_config = ConfigDict(extra="forbid")

    district: str
    start_date: date = Field(default_factory=lambda: date(2026, 10, 20))
    end_date: date = Field(default_factory=lambda: date(2026, 10, 23))
    current_date: date | None = None
    field_deadlines: dict[UUID, date] = Field(default_factory=dict)
    forecasts: list[DailyForecast] = Field(default_factory=list)
    previous_forecasts: list[DailyForecast] | None = None


class WeatherWindowOutput(BaseModel):
    """Evaluated weather window, workability, and replanning trigger status."""

    model_config = ConfigDict(extra="forbid")

    district: str = ""
    forecasts: list[DailyForecast] = Field(default_factory=list)
    is_rain_predicted: bool = False
    workable_days_count: int = 0
    advisory: str = "Clear weather; optimal harvesting and baling conditions."
    field_windows: list[FieldOperatingWindow] = Field(default_factory=list)
    is_replan_triggered: bool = False
    replan_reason: str | None = None
    replan_details: dict[str, str] = Field(default_factory=dict)


class WeatherWindowState(BaseModel):
    """LangGraph state schema for Weather & Window agent execution."""

    model_config = ConfigDict(extra="forbid")

    input: WeatherWindowInput
    output: WeatherWindowOutput | None = None
    status: str = "initialized"
    replan_event_emitted: bool = False
