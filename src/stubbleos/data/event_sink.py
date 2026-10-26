"""Persist every bus event to ``agent_events`` (durable, replayable log)."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from stubbleos.core.events import Event, EventBus, Subscription
from stubbleos.data.repositories import AgentEventRepository


class PersistingEventSink:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    async def __call__(self, event: Event) -> None:
        # Sync DB call; acceptable at Phase-1/simulation scale. Move to an async engine or a
        # worker queue if profiling shows event-loop stalls (tracked in ROADMAP).
        with self._factory() as session:
            AgentEventRepository(session).add(event)
            session.commit()

    def attach(self, bus: EventBus, pattern: str = "*") -> Subscription:
        return bus.subscribe(pattern, self)
