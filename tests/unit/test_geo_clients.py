"""Unit tests for STAC, FIRMS, and Open-Meteo clients testing caching, retries, timeouts, and fallbacks."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest
from shapely.geometry import Polygon

from stubbleos.geo.client import CachingGeoClient
from stubbleos.geo.firms import NasaFirmsClient
from stubbleos.geo.stac import Sentinel2StacClient
from stubbleos.geo.weather import OpenMeteoClient


@pytest.fixture
def geo_client() -> CachingGeoClient:
    return CachingGeoClient()


@pytest.mark.asyncio
async def test_geo_client_cache_hit(geo_client: CachingGeoClient) -> None:
    """Verifies that a subsequent call with identical parameters returns cached data."""
    test_url = "https://mock.geo.api/v1/test"
    params = {"district": "Sangrur"}

    # Seed the cache directly using client cache key
    key = geo_client.make_cache_key(test_url, params)
    geo_client._set_cache(key, {"key": "cached_val"}, ttl=3600.0)

    res = await geo_client.get_json(test_url, params=params)
    assert res.source == "cache"
    assert res.is_fallback is False
    assert res.data == {"key": "cached_val"}
    assert res.confidence_penalty == 0.0


@pytest.mark.asyncio
async def test_geo_client_timeout_and_fallback(geo_client: CachingGeoClient) -> None:
    """Verifies that a remote timeout degrades gracefully to the committed offline fixture."""
    test_url = "https://unreachable.stac.test/v1/search"

    # Mock httpx.AsyncClient.get to raise TimeoutError
    with patch("httpx.AsyncClient.get", side_effect=TimeoutError("Request timed out")):
        res = await geo_client.get_json(
            test_url,
            fixture_fallback_name="sentinel2_stac_sangrur.json",
        )

    assert res.source == "fixture"
    assert res.is_fallback is True
    assert res.confidence_penalty > 0.0
    assert "features" in res.data
    assert len(res.data["features"]) > 0


@pytest.mark.asyncio
async def test_geo_client_retry_with_backoff(geo_client: CachingGeoClient) -> None:
    """Verifies retry behavior on transient HTTP 500 error."""
    test_url = "https://flaky.api/v1/data"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "retried": True}
    mock_resp.raise_for_status = lambda: None

    attempts = 0

    async def flaky_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise httpx.HTTPStatusError("500 Internal Error", request=None, response=None)
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=flaky_get):
        res = await geo_client.get_json(test_url, ttl_seconds=60.0)

    assert attempts == 2
    assert res.data["status"] == "ok"
    assert res.source == "network"


@pytest.mark.asyncio
async def test_sentinel2_stac_client_fallback() -> None:
    """Tests Sentinel-2 STAC client fallback to committed fixture in offline environment."""
    client = Sentinel2StacClient()
    bbox = (75.70, 30.15, 76.15, 30.45)

    result = await client.search_scenes(
        bbox=bbox,
        start_date=date(2026, 10, 15),
        end_date=date(2026, 10, 26),
    )

    assert len(result.scenes) >= 2
    assert result.scenes[0].scene_id.startswith("S2")
    assert "red" in result.scenes[0].assets
    assert "nir" in result.scenes[0].assets
    # Should flag fallback when real external STAC API is offline
    assert result.is_fallback is True
    assert result.confidence_penalty > 0.0


@pytest.mark.asyncio
async def test_nasa_firms_client_and_spatial_filtering() -> None:
    """Tests NASA FIRMS client query, fallback, and spatial polygon intersection."""
    firms_client = NasaFirmsClient()
    bbox = (75.70, 30.15, 76.15, 30.45)

    search_res = await firms_client.get_active_fires(
        bbox=bbox,
        start_date=date(2026, 10, 20),
        end_date=date(2026, 10, 25),
    )

    assert len(search_res.hits) >= 3
    assert search_res.is_fallback is True

    # Spatial intersection: polygon enclosing the first hit at (lat 30.2451, lon 75.8342)
    hit_poly = Polygon(
        [
            (75.830, 30.240),
            (75.840, 30.240),
            (75.840, 30.250),
            (75.830, 30.250),
            (75.830, 30.240),
        ]
    )

    intersecting = NasaFirmsClient.filter_hits_for_polygon(
        hit_poly,
        search_res.hits,
        min_confidence_pct=50.0,
    )
    assert len(intersecting) == 1
    assert intersecting[0].latitude == pytest.approx(30.2451, abs=1e-4)

    # Distant polygon with no hits
    distant_poly = Polygon(
        [
            (75.50, 30.00),
            (75.51, 30.00),
            (75.51, 30.01),
            (75.50, 30.01),
            (75.50, 30.00),
        ]
    )
    assert len(NasaFirmsClient.filter_hits_for_polygon(distant_poly, search_res.hits)) == 0


@pytest.mark.asyncio
async def test_open_meteo_client_forecast_and_workability() -> None:
    """Tests Open-Meteo weather client forecast parsing and safe operating window workability under offline fallback."""
    weather_client = OpenMeteoClient()

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Network offline")):
        res = await weather_client.get_forecast(
            latitude=30.24,
            longitude=75.84,
            start_date=date(2026, 10, 20),
            end_date=date(2026, 10, 26),
        )

    assert res.is_fallback is True
    assert res.confidence_penalty > 0.0
    assert len(res.forecasts) == 7
    # Day 0 (2026-10-20) has 0 rain, wind 12.2 km/h -> workable
    assert res.forecasts[0].is_workable is True

    # Day 3 (2026-10-23) has 12.5mm rain > threshold 2.0mm -> unworkable
    assert res.forecasts[3].precipitation_mm == pytest.approx(12.5, abs=0.1)
    assert res.forecasts[3].is_workable is False

    # Day 4 (2026-10-24) has 8.4mm rain -> unworkable
    assert res.forecasts[4].is_workable is False

    # Day 5 (2026-10-25) has 0 rain -> workable
    assert res.forecasts[5].is_workable is True
