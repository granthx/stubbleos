# Weather & Window Agent (Phase 4 Skeleton)

## Purpose
The Weather & Window agent forecasts local weather conditions (precipitation, humidity, soil moisture) to compute feasible operational windows for machinery dispatch and baling.

## Typed Contract
- Input: `WeatherWindowInput` (district, date range).
- Output: `WeatherWindowOutput` (daily workability status, rain probability, agronomic advisory).
- State: `WeatherWindowState`.

## Tools
- `fetch_weather_forecast_mock`: Simulates precipitation and temperature predictions.
- `check_drying_conditions_mock`: Evaluates straw moisture evaporation rates.
