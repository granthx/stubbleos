"""Open-Meteo weather forecast client with caching, workability evaluation, and offline fixture fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from stubbleos.core.config import Settings, get_settings
from stubbleos.core.logging import get_logger
from stubbleos.geo.client import CachingGeoClient

log = get_logger(__name__)


@dataclass
class DailyWeatherForecast:
    forecast_date: date
    precipitation_mm: float
    wind_speed_max_kmh: float
    temp_max_c: float
    temp_min_c: float
    humidity_mean_pct: float
    soil_moisture_index: float
    is_workable: bool


@dataclass
class WeatherForecastResult:
    forecasts: list[DailyWeatherForecast]
    source: str
    is_fallback: bool
    confidence_penalty: float


class OpenMeteoClient:
    """Client for querying agricultural weather forecasts from Open-Meteo API."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        geo_client: CachingGeoClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.geo_client = geo_client or CachingGeoClient(settings=self.settings)

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> WeatherForecastResult:
        """Fetches daily forecast for agricultural operations.

        Degrades gracefully to committed offline fixtures on network failure.
        """
        url = self.settings.open_meteo_url
        params: dict[str, Any] = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": [
                "precipitation_sum",
                "wind_speed_10m_max",
                "temperature_2m_max",
                "temperature_2m_min",
                "relative_humidity_2m_mean",
                "soil_moisture_0_to_7cm_mean",
            ],
            "timezone": "Asia/Kolkata",
        }

        try:
            cached_res = await self.geo_client.get_json(
                url,
                params=params,
                fixture_fallback_name="open_meteo_sangrur.json",
            )
        except Exception as exc:
            log.warning("open_meteo_query_failed_using_fixture", error=str(exc))
            fixture_data = self.geo_client.load_fixture("open_meteo_sangrur.json")
            from stubbleos.geo.client import CachedResponse

            cached_res = CachedResponse(
                data=fixture_data,
                timestamp=0.0,
                ttl=0.0,
                source="fixture",
                is_fallback=True,
                confidence_penalty=0.15,
            )

        daily = cached_res.data.get("daily", {})
        times = daily.get("time", [])
        precips = daily.get("precipitation_sum", [])
        winds = daily.get("wind_speed_10m_max", [])
        t_maxs = daily.get("temperature_2m_max", [])
        t_mins = daily.get("temperature_2m_min", [])
        humidities = daily.get("relative_humidity_2m_mean", [])
        soil_moistures = daily.get("soil_moisture_0_to_7cm_mean", [])

        forecasts: list[DailyWeatherForecast] = []
        max_rain = self.settings.max_workable_rain_mm
        max_wind = self.settings.max_workable_wind_kmh
        max_soil = self.settings.max_soil_moisture_index

        for i, t_str in enumerate(times):
            f_date = date.fromisoformat(t_str)
            p_val = float(precips[i]) if i < len(precips) else 0.0
            w_val = float(winds[i]) if i < len(winds) else 10.0
            t_max = float(t_maxs[i]) if i < len(t_maxs) else 30.0
            t_min = float(t_mins[i]) if i < len(t_mins) else 18.0
            h_val = float(humidities[i]) if i < len(humidities) else 50.0
            s_val = float(soil_moistures[i]) if i < len(soil_moistures) else 0.20

            # Workability check: rain <= max_rain, wind <= max_wind, soil moisture <= max_soil
            workable = (p_val <= max_rain) and (w_val <= max_wind) and (s_val <= max_soil)

            forecasts.append(
                DailyWeatherForecast(
                    forecast_date=f_date,
                    precipitation_mm=p_val,
                    wind_speed_max_kmh=w_val,
                    temp_max_c=t_max,
                    temp_min_c=t_min,
                    humidity_mean_pct=h_val,
                    soil_moisture_index=s_val,
                    is_workable=workable,
                )
            )

        return WeatherForecastResult(
            forecasts=forecasts,
            source=cached_res.source,
            is_fallback=cached_res.is_fallback,
            confidence_penalty=cached_res.confidence_penalty,
        )
