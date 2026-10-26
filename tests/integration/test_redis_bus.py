"""Needs Redis at STUBBLEOS_REDIS_URL. Run: make up && make test-int"""

import asyncio
import uuid

import pytest

from stubbleos.core.config import Settings
from stubbleos.core.events import Event, FieldStateChanged, RedisEventBus
from stubbleos.core.types import FieldState

pytestmark = pytest.mark.integration


async def test_publish_is_received_by_listener() -> None:
    url = Settings(_env_file=None).redis_url  # type: ignore[call-arg]
    bus = RedisEventBus(url)
    try:
        await bus._redis.ping()
    except Exception:
        pytest.skip("no Redis reachable")
    got: list[Event] = []

    async def handler(e: Event) -> None:
        got.append(e)

    bus.subscribe("field.*", handler)
    await bus.start()
    try:
        await asyncio.sleep(0.1)
        p = FieldStateChanged(field_id=uuid.uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.5)
        sent = await bus.emit(p, source="t")
        for _ in range(50):
            if got:
                break
            await asyncio.sleep(0.05)
        assert got
        assert got[0].event_id == sent.event_id
    finally:
        await bus.stop()
