from datetime import UTC, datetime

import pytest

from stubbleos.core.clock import SimClock
from stubbleos.core.config import Settings
from stubbleos.core.events import InMemoryEventBus
from stubbleos.core.ids import SeededUUIDFactory

T0 = datetime(2026, 10, 20, 6, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, env="test", llm_provider="fake")  # type: ignore[call-arg]


@pytest.fixture
def clock() -> SimClock:
    return SimClock(T0)


@pytest.fixture
def bus(clock: SimClock) -> InMemoryEventBus:
    return InMemoryEventBus(clock=clock, id_factory=SeededUUIDFactory(1))
