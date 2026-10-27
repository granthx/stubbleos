# Weather & Window Agent

The **Weather & Window Agent** evaluates agricultural operating windows for harvesting, baling, and sowing operations based on multi-day meteorological forecasts from Open-Meteo.

## Responsibilities
- Computes safe operating windows per field by checking:
  - Precipitation $\le \text{max\_workable\_rain\_mm}$ (default 2.0 mm).
  - Wind speed $\le \text{max\_workable\_wind\_kmh}$ (default 35.0 km/h).
  - Soil moisture index $\le \text{max\_soil\_moisture\_index}$ (default 0.40).
- Tracks days remaining to each field's wheat sowing deadline and identifies contiguous blocks of workable days.
- Detects forecast shifts (e.g. rain delta $\ge \text{threshold}$) and automatically emits `ReplanTriggered` domain events.
