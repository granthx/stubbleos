"""NASA FIRMS active fire client with caching, spatial filtering, and offline fixture fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from shapely.geometry import Point, Polygon

from stubbleos.core.config import Settings, get_settings
from stubbleos.core.logging import get_logger
from stubbleos.geo.client import CachingGeoClient

log = get_logger(__name__)


@dataclass
class FirmsFireHit:
    latitude: float
    longitude: float
    brightness: float
    acq_date: str
    acq_time: str
    satellite: str
    confidence_pct: float
    frp: float


@dataclass
class FirmsSearchResult:
    hits: list[FirmsFireHit]
    source: str
    is_fallback: bool
    confidence_penalty: float


class NasaFirmsClient:
    """Client for querying active fire thermal anomalies (VIIRS/MODIS) from NASA FIRMS."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        geo_client: CachingGeoClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.geo_client = geo_client or CachingGeoClient(settings=self.settings)

    async def get_active_fires(
        self,
        bbox: tuple[float, float, float, float],
        start_date: date,
        end_date: date,
        *,
        source: str = "VIIRS_SNPP_NRT",
    ) -> FirmsSearchResult:
        """Fetches active fire anomalies for bounding box and date range.

        Degrades gracefully to committed offline fixtures on network failure or missing API key.
        """
        api_key_sec = self.settings.firms_api_key
        api_key = api_key_sec.get_secret_value() if api_key_sec else None

        # If no FIRMS API key is configured or offline sandbox, directly fallback to committed fixture
        if not api_key:
            fixture_data = self.geo_client.load_fixture("firms_sangrur.json")
            from stubbleos.geo.client import CachedResponse

            cached_res = CachedResponse(
                data=fixture_data,
                timestamp=0.0,
                ttl=0.0,
                source="fixture",
                is_fallback=True,
                confidence_penalty=0.15,
            )
        else:
            days = max(1, (end_date - start_date).days + 1)
            # Standard FIRMS API format: /api/area/csv/[MAP_KEY]/[SOURCE]/[BBOX]/[DAYS]
            bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
            url = f"{self.settings.firms_api_url.rstrip('/')}/{api_key}/{source}/{bbox_str}/{days}"
            try:
                cached_res = await self.geo_client.get_json(
                    url,
                    fixture_fallback_name="firms_sangrur.json",
                )
            except Exception as exc:
                log.warning("firms_query_failed_using_fixture", error=str(exc))
                fixture_data = self.geo_client.load_fixture("firms_sangrur.json")
                from stubbleos.geo.client import CachedResponse

                cached_res = CachedResponse(
                    data=fixture_data,
                    timestamp=0.0,
                    ttl=0.0,
                    source="fixture",
                    is_fallback=True,
                    confidence_penalty=0.20,
                )

        hits: list[FirmsFireHit] = []
        records = cached_res.data.get("records", [])
        for rec in records:
            lat = float(rec.get("latitude", 0.0))
            lon = float(rec.get("longitude", 0.0))
            conf = rec.get("confidence", "nominal")
            conf_pct = float(
                rec.get(
                    "confidence_pct",
                    90.0 if conf == "high" else (65.0 if conf == "nominal" else 35.0),
                )
            )

            hits.append(
                FirmsFireHit(
                    latitude=lat,
                    longitude=lon,
                    brightness=float(rec.get("brightness", 320.0)),
                    acq_date=str(rec.get("acq_date", "")),
                    acq_time=str(rec.get("acq_time", "")),
                    satellite=str(rec.get("satellite", "VIIRS")),
                    confidence_pct=conf_pct,
                    frp=float(rec.get("frp", 10.0)),
                )
            )

        return FirmsSearchResult(
            hits=hits,
            source=cached_res.source,
            is_fallback=cached_res.is_fallback,
            confidence_penalty=cached_res.confidence_penalty,
        )

    @staticmethod
    def filter_hits_for_polygon(
        polygon: Polygon | Any,
        hits: list[FirmsFireHit],
        *,
        min_confidence_pct: float = 50.0,
        buffer_degrees: float = 0.002,  # ~200m buffer for GPS/scan drift
    ) -> list[FirmsFireHit]:
        """Filters fire hits that intersect a field geometry with confidence above threshold."""
        buffered_poly = polygon.buffer(buffer_degrees) if hasattr(polygon, "buffer") else polygon
        intersecting: list[FirmsFireHit] = []

        for hit in hits:
            if hit.confidence_pct < min_confidence_pct:
                continue
            pt = Point(hit.longitude, hit.latitude)
            if (hasattr(buffered_poly, "contains") and buffered_poly.contains(pt)) or (
                hasattr(buffered_poly, "intersects") and buffered_poly.intersects(pt)
            ):
                intersecting.append(hit)

        return intersecting
