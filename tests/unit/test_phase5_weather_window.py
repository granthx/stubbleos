"""Unit tests for Weather & Window agent."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from stubbleos.agents.weather_window.graph import build_weather_window_graph
from stubbleos.agents.weather_window.logic import (
    build_replan_event,
    evaluate_weather_window,
    find_contiguous_workable_blocks,
)
from stubbleos.agents.weather_window.schemas import (
    DailyForecast,
    WeatherWindowInput,
    WeatherWindowState,
)
from stubbleos.core.events import InMemoryEventBus
from stubbleos.core.types import ReplanReason


def test_contiguous_workable_blocks() -> None:
    """Verifies that contiguous workable sequences are correctly identified."""
    d0 = date(2026, 10, 20)
    forecasts = [
        DailyForecast(forecast_date=d0, is_workable=True),
        DailyForecast(forecast_date=d0 + timedelta(days=1), is_workable=True),
        DailyForecast(forecast_date=d0 + timedelta(days=2), is_workable=False),  # Rain
        DailyForecast(forecast_date=d0 + timedelta(days=3), is_workable=True),
        DailyForecast(forecast_date=d0 + timedelta(days=4), is_workable=True),
        DailyForecast(forecast_date=d0 + timedelta(days=5), is_workable=False),  # High wind
    ]

    blocks = find_contiguous_workable_blocks(forecasts)
    assert len(blocks) == 2
    assert blocks[0] == (d0, d0 + timedelta(days=1))
    assert blocks[1] == (d0 + timedelta(days=3), d0 + timedelta(days=4))


def test_weather_window_safe_operations_and_deadlines() -> None:
    """Verifies per-field deadline tracking and urgency classification."""
    current_dt = date(2026, 10, 20)
    f1 = uuid.uuid4()
    f2 = uuid.uuid4()

    # Field 1 has 3 days to deadline; Field 2 has 12 days to deadline
    deadlines = {
        f1: current_dt + timedelta(days=3),
        f2: current_dt + timedelta(days=12),
    }

    forecasts = [
        DailyForecast(forecast_date=current_dt, is_workable=True),
        DailyForecast(forecast_date=current_dt + timedelta(days=1), precipitation_mm=10.0, is_workable=False),
        DailyForecast(forecast_date=current_dt + timedelta(days=2), precipitation_mm=8.0, is_workable=False),
        DailyForecast(forecast_date=current_dt + timedelta(days=3), is_workable=True),
    ]

    inp = WeatherWindowInput(
        district="Sangrur",
        current_date=current_dt,
        field_deadlines=deadlines,
        forecasts=forecasts,
    )
    out = evaluate_weather_window(inp)

    f1_win = next(w for w in out.field_windows if w.field_id == f1)
    f2_win = next(w for w in out.field_windows if w.field_id == f2)

    assert f1_win.days_remaining_to_deadline == 3
    # Field 1 has 3 days remaining and only 2 workable days -> high urgency
    assert f1_win.urgency_level in {"high", "critical"}

    assert f2_win.days_remaining_to_deadline == 12
    assert f2_win.urgency_level == "low"


def test_weather_window_replan_triggered_on_rain_shock() -> None:
    """Verifies that a forecast shift in precipitation triggers a ReplanTriggered event."""
    d0 = date(2026, 10, 20)
    d1 = date(2026, 10, 21)

    prev_forecasts = [
        DailyForecast(forecast_date=d0, precipitation_mm=0.0),
        DailyForecast(forecast_date=d1, precipitation_mm=0.0),
    ]

    # Shift: 15mm sudden unpredicted rain on d1 (delta 15.0mm >= threshold 5.0mm)
    new_forecasts = [
        DailyForecast(forecast_date=d0, precipitation_mm=0.0),
        DailyForecast(forecast_date=d1, precipitation_mm=15.0, is_workable=False),
    ]

    inp = WeatherWindowInput(
        district="Sangrur",
        current_date=d0,
        forecasts=new_forecasts,
        previous_forecasts=prev_forecasts,
    )

    out = evaluate_weather_window(inp)
    assert out.is_replan_triggered is True
    assert out.replan_reason == "rain_forecast_change"
    assert "15.0" in out.replan_details["max_rain_delta_mm"]

    event = build_replan_event(out)
    assert event is not None
    assert event.reason == ReplanReason.RAIN_FORECAST_CHANGE
    assert event.district == "Sangrur"


def test_weather_window_graph_execution() -> None:
    """Verifies LangGraph state execution with event emission."""
    d0 = date(2026, 10, 20)
    event_bus = InMemoryEventBus()

    inp = WeatherWindowInput(
        district="Sangrur",
        current_date=d0,
        forecasts=[
            DailyForecast(forecast_date=d0, precipitation_mm=20.0, is_workable=False),
        ],
        previous_forecasts=[
            DailyForecast(forecast_date=d0, precipitation_mm=0.0),
        ],
    )

    state = WeatherWindowState(input=inp)
    graph = build_weather_window_graph(event_bus=event_bus)
    result_state = graph.invoke(state, config={"configurable": {"thread_id": "ww_test"}})

    assert result_state["status"] == "completed"
    assert result_state["replan_event_emitted"] is True
    assert len(event_bus.history) == 1
    assert event_bus.history[0].event_type == "plan.replan_triggered"
