"""Minimal API for Phase 1: liveness, readiness and Prometheus metrics.

Rate limiting, auth, input schemas and websockets arrive with the full API in Phase 7.
"""

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from stubbleos import __version__
from stubbleos.core.config import Settings, get_settings
from stubbleos.core.logging import configure_logging

ReadinessCheck = Callable[[], bool]


def default_readiness_checks(settings: Settings) -> dict[str, ReadinessCheck]:
    def database() -> bool:
        from sqlalchemy import create_engine, text

        engine = create_engine(settings.database_url, connect_args={"connect_timeout": 2})
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        finally:
            engine.dispose()

    def redis() -> bool:
        import redis as redis_sync

        client = redis_sync.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        try:
            return bool(client.ping())
        finally:
            client.close()

    return {"database": database, "redis": redis}


def create_app(
    settings: Settings | None = None, readiness_checks: dict[str, ReadinessCheck] | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)
    checks = readiness_checks if readiness_checks is not None else default_readiness_checks(settings)
    app = FastAPI(title="StubbleOS", version=__version__)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        results: dict[str, bool] = {}
        for name, check in checks.items():
            try:
                results[name] = bool(check())
            except Exception:
                results[name] = False
        ready = all(results.values())
        return JSONResponse(
            {"status": "ready" if ready else "degraded", "checks": results},
            status_code=200 if ready else 503,
        )

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
