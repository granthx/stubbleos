"""Pure logic for evaluating operating windows and detecting weather shocks."""

from __future__ import annotations

from datetime import date, timedelta

from stubbleos.agents.weather_window.schemas import (
    DailyForecast,
    FieldOperatingWindow,
    WeatherWindowInput,
    WeatherWindowOutput,
)
from stubbleos.core.config import Settings, get_settings
from stubbleos.core.events import ReplanTriggered
from stubbleos.core.types import ReplanReason


def find_contiguous_workable_blocks(
    forecasts: list[DailyForecast],
) -> list[tuple[date, date]]:
    """Identifies continuous sequences of workable days."""
    blocks: list[tuple[date, date]] = []
    block_start: date | None = None
    last_date: date | None = None

    for f in sorted(forecasts, key=lambda x: x.forecast_date):
        if f.is_workable:
            if block_start is None:
                block_start = f.forecast_date
            last_date = f.forecast_date
        else:
            if block_start is not None and last_date is not None:
                blocks.append((block_start, last_date))
                block_start = None
                last_date = None

    if block_start is not None and last_date is not None:
        blocks.append((block_start, last_date))

    return blocks


def evaluate_weather_window(
    input_data: WeatherWindowInput,
    settings: Settings | None = None,
) -> WeatherWindowOutput:
    """Computes district forecasts, per-field workable windows, and replanning shock triggers."""
    cfg = settings or get_settings()

    # If forecasts not provided, generate from start_date to end_date
    forecasts = list(input_data.forecasts)
    if not forecasts and input_data.start_date and input_data.end_date:
        curr = input_data.start_date
        while curr <= input_data.end_date:
            forecasts.append(
                DailyForecast(
                    forecast_date=curr,
                    precipitation_mm=0.0,
                    wind_speed_max_kmh=12.0,
                    temp_max_c=31.0,
                    temp_min_c=18.0,
                    humidity_mean_pct=45.0,
                    soil_moisture_index=0.18,
                    is_workable=True,
                )
            )
            curr += timedelta(days=1)

    workable_count = sum(1 for f in forecasts if f.is_workable)
    is_rain = any(f.precipitation_mm > cfg.max_workable_rain_mm for f in forecasts)

    advisory = (
        "Advisory: Imminent rain forecast requires prioritizing smallholder harvest operations."
        if is_rain
        else "Optimal drying conditions; baling and in-situ operations safe to proceed."
    )

    current_dt = input_data.current_date or (
        forecasts[0].forecast_date if forecasts else input_data.start_date
    )

    # Per-field windows
    field_windows: list[FieldOperatingWindow] = []
    for f_id, deadline in input_data.field_deadlines.items():
        days_rem = (deadline - current_dt).days
        rel_forecasts = [f for f in forecasts if current_dt <= f.forecast_date <= deadline]
        w_days = sum(1 for f in rel_forecasts if f.is_workable)
        blocks = find_contiguous_workable_blocks(rel_forecasts)

        if days_rem <= 3 and w_days <= 1:
            urgency = "critical"
            f_adv = "CRITICAL: Urgent clearance required before sowing deadline."
        elif days_rem <= 5 and w_days <= 2:
            urgency = "high"
            f_adv = "HIGH: Rain predicted soon; dispatch machines immediately."
        elif days_rem <= 10:
            urgency = "medium"
            f_adv = "MEDIUM: Operations progressing within safe window."
        else:
            urgency = "low"
            f_adv = "LOW: Ample days remaining to deadline."

        field_windows.append(
            FieldOperatingWindow(
                field_id=f_id,
                sowing_deadline=deadline,
                days_remaining_to_deadline=days_rem,
                total_workable_days=w_days,
                safe_operating_windows=blocks,
                urgency_level=urgency,
                advisory=f_adv,
            )
        )

    # Replan trigger detection
    is_replan = False
    replan_reason = None
    replan_details: dict[str, str] = {}

    if input_data.previous_forecasts:
        prev_map = {f.forecast_date: f for f in input_data.previous_forecasts}
        max_shift = 0.0
        shift_date: date | None = None

        for f in forecasts:
            if f.forecast_date in prev_map:
                prev_f = prev_map[f.forecast_date]
                shift = abs(f.precipitation_mm - prev_f.precipitation_mm)
                if shift > max_shift:
                    max_shift = shift
                    shift_date = f.forecast_date

        threshold = cfg.replan_rain_delta_threshold_mm
        if max_shift >= threshold and shift_date is not None:
            is_replan = True
            replan_reason = "rain_forecast_change"
            replan_details = {
                "max_rain_delta_mm": f"{max_shift:.1f}",
                "shift_date": shift_date.isoformat(),
                "threshold_mm": f"{threshold:.1f}",
                "district": input_data.district,
            }

    return WeatherWindowOutput(
        district=input_data.district,
        forecasts=forecasts,
        is_rain_predicted=is_rain,
        workable_days_count=workable_count,
        advisory=advisory,
        field_windows=field_windows,
        is_replan_triggered=is_replan,
        replan_reason=replan_reason,
        replan_details=replan_details,
    )


# Backward compatible alias
evaluate_weather_windows = evaluate_weather_window


def build_replan_event(output: WeatherWindowOutput) -> ReplanTriggered | None:
    """Builds a ReplanTriggered domain event if a significant weather shock was detected."""
    if not output.is_replan_triggered:
        return None

    return ReplanTriggered(
        district=output.district,
        reason=ReplanReason.RAIN_FORECAST_CHANGE,
        details=output.replan_details,
    )
