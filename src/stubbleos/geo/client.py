"""Resilient caching HTTP client for geospatial APIs with retries and offline fixture fallback."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from stubbleos.core.config import Settings, get_settings
from stubbleos.core.logging import get_logger
from stubbleos.core.retry import retry_async

log = get_logger(__name__)


@dataclass
class CachedResponse:
    data: Any
    timestamp: float
    ttl: float
    source: str  # "network" | "cache" | "fixture"
    is_fallback: bool = False
    confidence_penalty: float = 0.0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl


class CachingGeoClient:
    """HTTP client that caches responses in-memory/disk and falls back to offline fixtures on failure."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.cache_dir = cache_dir or Path(".geo_cache")
        self._memory_cache: dict[str, CachedResponse] = {}

    def _get_cache(self, key: str, allow_stale: bool = False) -> CachedResponse | None:
        entry = self._memory_cache.get(key)
        if entry is not None:
            if not entry.is_expired:
                return CachedResponse(
                    data=entry.data,
                    timestamp=entry.timestamp,
                    ttl=entry.ttl,
                    source="cache",
                    is_fallback=False,
                    confidence_penalty=0.0,
                )
            if allow_stale:
                return CachedResponse(
                    data=entry.data,
                    timestamp=entry.timestamp,
                    ttl=entry.ttl,
                    source="cache",
                    is_fallback=True,
                    confidence_penalty=0.15,
                )
        return None

    def _set_cache(self, key: str, data: Any, ttl: float) -> None:
        self._memory_cache[key] = CachedResponse(
            data=data,
            timestamp=time.time(),
            ttl=ttl,
            source="network",
            is_fallback=False,
            confidence_penalty=0.0,
        )

    def load_fixture(self, fixture_name: str) -> Any:
        """Load offline fixture committed in tests/fixtures."""
        fixtures_dir = Path(self.settings.offline_fixtures_dir)
        fixture_path = fixtures_dir / fixture_name
        if not fixture_path.exists():
            # Try workspace root relative
            fixture_path = Path("tests/fixtures") / fixture_name
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture {fixture_name} not found at {fixture_path}")

        with open(fixture_path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def make_cache_key(url: str, params: dict[str, Any] | None = None) -> str:
        """Computes deterministic cache key for a URL and query params."""
        return f"{url}?{json.dumps(params or {}, sort_keys=True)}"

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        fixture_fallback_name: str | None = None,
        ttl_seconds: float | None = None,
    ) -> CachedResponse:
        """Fetches JSON with caching, retries with backoff, and offline fixture fallback."""
        cache_key = self.make_cache_key(url, params)
        ttl = ttl_seconds if ttl_seconds is not None else float(self.settings.geo_cache_ttl_seconds)

        # 1. Check active cache
        cached = self._get_cache(cache_key, allow_stale=False)
        if cached is not None:
            return cached

        # 2. Attempt remote HTTP call with retry and timeout
        timeout = self.settings.geo_client_timeout_s
        retries = self.settings.geo_client_max_retries

        async def _call() -> Any:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(url, params=params, headers=headers)
                res.raise_for_status()
                return res.json()

        try:
            data = await retry_async(
                _call,
                attempts=retries,
                base_delay=0.3,
                max_delay=2.0,
                timeout_s=timeout,
                retry_on=(httpx.HTTPError, TimeoutError, OSError),
            )
            self._set_cache(cache_key, data, ttl)
            return CachedResponse(
                data=data,
                timestamp=time.time(),
                ttl=ttl,
                source="network",
                is_fallback=False,
                confidence_penalty=0.0,
            )
        except Exception as exc:
            log.warning(
                "geo_remote_call_failed",
                url=url,
                error=str(exc),
                fallback_fixture=fixture_fallback_name,
            )

            # 3. Degrade gracefully to stale cache if available
            stale = self._get_cache(cache_key, allow_stale=True)
            if stale is not None:
                return stale

            # 4. Fallback to committed offline fixture
            if fixture_fallback_name:
                fixture_data = self.load_fixture(fixture_fallback_name)
                return CachedResponse(
                    data=fixture_data,
                    timestamp=time.time(),
                    ttl=ttl,
                    source="fixture",
                    is_fallback=True,
                    confidence_penalty=0.20,
                )

            raise exc
