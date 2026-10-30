"""Production FastAPI application with REST v1 routes, WebSockets, and health checks."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from stubbleos import __version__
from stubbleos.api.routes.approvals import router as approvals_router
from stubbleos.api.routes.bookings import router as bookings_router
from stubbleos.api.routes.channels import router as channels_router
from stubbleos.api.routes.contracts import router as contracts_router
from stubbleos.api.routes.district import router as district_router
from stubbleos.api.routes.fields import router as fields_router
from stubbleos.api.routes.machines import router as machines_router
from stubbleos.api.routes.mrv import router as mrv_router
from stubbleos.api.routes.plans import router as plans_router
from stubbleos.api.websocket import ws_manager
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

    app = FastAPI(
        title="StubbleOS Coordination API",
        version=__version__,
        description="Autonomous coordination layer for crop-residue management in Punjab/Haryana.",
    )

    # CORS configuration for Next.js frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount REST v1 routers
    v1_routers = [
        fields_router,
        machines_router,
        plans_router,
        bookings_router,
        approvals_router,
        contracts_router,
        channels_router,
        mrv_router,
        district_router,
    ]
    for r in v1_routers:
        app.include_router(r, prefix="/api/v1")

    # Real-time WebSocket streaming endpoint
    @app.websocket("/ws/district/{district}")
    async def websocket_district_endpoint(websocket: WebSocket, district: str) -> None:
        await ws_manager.connect(websocket, district=district)
        try:
            while True:
                # Keep alive / listen for client ping or filter requests
                data = await websocket.receive_text()
                # Echo back acknowledgment
                await websocket.send_json({"type": "ack", "received": data})
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, district=district)

    # Health and Prometheus metrics
    @app.get("/healthz", tags=["Health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/readyz", tags=["Health"])
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

    @app.get("/metrics", tags=["Health"])
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
