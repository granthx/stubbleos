"""WebSocket manager for real-time district telemetry and event streaming."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from stubbleos.core.events import Event, EventBus
from stubbleos.core.logging import get_logger

log = get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped by district."""

    def __init__(self) -> None:
        self.active_connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, district: str = "sangrur") -> None:
        await websocket.accept()
        self.active_connections[district.lower()].add(websocket)
        log.info("ws_client_connected", district=district)

    def disconnect(self, websocket: WebSocket, district: str = "sangrur") -> None:
        self.active_connections[district.lower()].discard(websocket)
        log.info("ws_client_disconnected", district=district)

    async def broadcast_to_district(self, district: str, data: dict[str, Any]) -> None:
        payload = json.dumps(data)
        stale = set()
        for connection in self.active_connections.get(district.lower(), set()):
            try:
                await connection.send_text(payload)
            except Exception:
                stale.add(connection)
        for dead in stale:
            self.active_connections[district.lower()].discard(dead)

    async def broadcast_all(self, data: dict[str, Any]) -> None:
        for dist in list(self.active_connections.keys()):
            await self.broadcast_to_district(dist, data)


ws_manager = ConnectionManager()


def wire_event_bus_to_websocket(event_bus: EventBus, manager: ConnectionManager = ws_manager) -> None:
    """Subscribes to EventBus and streams domain events over WebSockets."""

    async def event_forwarder(event: Event) -> None:
        msg = {
            "type": "domain_event",
            "event_type": event.event_type,
            "source": event.source,
            "timestamp": event.ts.isoformat(),
            "district": event.district,
            "payload": event.payload,
        }
        if event.district:
            await manager.broadcast_to_district(event.district, msg)
        else:
            await manager.broadcast_all(msg)

    event_bus.subscribe("*", event_forwarder)
