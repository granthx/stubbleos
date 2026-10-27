"""STAC client for Sentinel-2 L2A optical imagery with caching and offline fixture fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from stubbleos.core.config import Settings, get_settings
from stubbleos.core.logging import get_logger
from stubbleos.geo.client import CachingGeoClient

log = get_logger(__name__)


@dataclass
class Sentinel2Scene:
    scene_id: str
    datetime: datetime
    cloud_cover_pct: float
    bbox: tuple[float, float, float, float]
    assets: dict[str, str]


@dataclass
class Sentinel2StacSearchResult:
    scenes: list[Sentinel2Scene]
    source: str
    is_fallback: bool
    confidence_penalty: float


class Sentinel2StacClient:
    """Client for querying Sentinel-2 L2A STAC items over farm coordinates."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        geo_client: CachingGeoClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.geo_client = geo_client or CachingGeoClient(settings=self.settings)

    async def search_scenes(
        self,
        bbox: tuple[float, float, float, float],
        start_date: date,
        end_date: date,
        *,
        max_cloud_cover_pct: float = 30.0,
    ) -> Sentinel2StacSearchResult:
        """Searches Sentinel-2 scenes for given bbox and date range.

        Degrades gracefully to offline committed fixtures on network failure or sandbox isolation.
        """
        date_str = f"{start_date.isoformat()}/{end_date.isoformat()}"
        url = f"{self.settings.stac_api_url.rstrip('/')}/search"
        params: dict[str, Any] = {
            "collections": ["sentinel-2-l2a"],
            "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "datetime": date_str,
            "query": f'{{"eo:cloud_cover": {{"lte": {max_cloud_cover_pct}}}}}',
            "limit": 10,
        }

        try:
            cached_res = await self.geo_client.get_json(
                url,
                params=params,
                fixture_fallback_name="sentinel2_stac_sangrur.json",
            )
        except Exception as exc:
            log.warning("stac_query_failed_using_fixture", error=str(exc))
            fixture_data = self.geo_client.load_fixture("sentinel2_stac_sangrur.json")
            from stubbleos.geo.client import CachedResponse

            cached_res = CachedResponse(
                data=fixture_data,
                timestamp=0.0,
                ttl=0.0,
                source="fixture",
                is_fallback=True,
                confidence_penalty=0.20,
            )

        scenes: list[Sentinel2Scene] = []
        features = cached_res.data.get("features", [])
        for feat in features:
            props = feat.get("properties", {})
            dt_str = props.get("datetime", "")
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now()

            assets_raw = feat.get("assets", {})
            assets = {k: v.get("href", "") for k, v in assets_raw.items() if isinstance(v, dict)}
            f_bbox = tuple(feat.get("bbox", bbox))
            if len(f_bbox) == 4:
                bbox_4 = (float(f_bbox[0]), float(f_bbox[1]), float(f_bbox[2]), float(f_bbox[3]))
            else:
                bbox_4 = bbox

            scenes.append(
                Sentinel2Scene(
                    scene_id=feat.get("id", "unknown_s2_scene"),
                    datetime=dt,
                    cloud_cover_pct=float(props.get("eo:cloud_cover", 0.0)),
                    bbox=bbox_4,
                    assets=assets,
                )
            )

        return Sentinel2StacSearchResult(
            scenes=scenes,
            source=cached_res.source,
            is_fallback=cached_res.is_fallback,
            confidence_penalty=cached_res.confidence_penalty,
        )
