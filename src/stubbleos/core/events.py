"""Typed event envelope, payload registry and event buses.

Agents never exchange free text. They emit ``EventPayload`` subclasses registered under a
dotted event type; the bus validates the type on publish and subscribers recover the typed
payload with ``Event.typed_payload()``.

Delivery semantics:
* ``InMemoryEventBus``: handlers are awaited sequentially in subscription order, which keeps
  simulation runs deterministic. Handler failures are isolated into ``dead_letters``.
* ``RedisEventBus``: at-most-once pub/sub across processes. Durability comes from persisting
  every event to the ``agent_events`` table (see ``data/event_sink.py``), not from Redis.
"""

from __future__ import annotations

import asyncio
import contextlib
import fnmatch
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Literal, Self, TypeVar
from uuid import UUID, uuid4

from pydantic import Field, ValidationError

from stubbleos.core.clock import Clock, SystemClock, require_aware
from stubbleos.core.ids import IdFactory
from stubbleos.core.logging import get_logger
from stubbleos.core.metrics import EVENTS_PUBLISHED, HANDLER_ERRORS
from stubbleos.core.types import (
    ApprovalStatus,
    Channel,
    Confidence,
    FieldState,
    Language,
    MachineType,
    ReplanReason,
    ServiceType,
    StrictModel,
)

log = get_logger(__name__)

MAX_DISPATCH_DEPTH = 50


class EventBusError(RuntimeError):
    pass


class UnknownEventTypeError(KeyError):
    pass


UnknownEventType = UnknownEventTypeError


# --------------------------------------------------------------------------- payload registry

_REGISTRY: dict[str, type[EventPayload]] = {}
P = TypeVar("P", bound="EventPayload")


class EventPayload(StrictModel):
    """Base class for typed messages. Subclasses must be decorated with ``@register_event``."""

    event_type: ClassVar[str]


def register_event(event_type: str) -> Callable[[type[P]], type[P]]:
    def decorator(cls: type[P]) -> type[P]:
        existing = _REGISTRY.get(event_type)
        if existing is not None and existing is not cls:
            raise ValueError(f"event type {event_type!r} already registered to {existing.__name__}")
        cls.event_type = event_type
        _REGISTRY[event_type] = cls
        return cls

    return decorator


def get_payload_type(event_type: str) -> type[EventPayload]:
    try:
        return _REGISTRY[event_type]
    except KeyError:
        raise UnknownEventType(event_type) from None


def registered_event_types() -> list[str]:
    return sorted(_REGISTRY)


# --------------------------------------------------------------------------- envelope


class Event(StrictModel):
    event_id: UUID
    event_type: str
    source: str
    ts: datetime
    correlation_id: UUID | None = None
    district: str | None = None
    payload: dict[str, Any]

    @classmethod
    def create(
        cls,
        payload: EventPayload,
        *,
        source: str,
        ts: datetime,
        event_id: UUID | None = None,
        correlation_id: UUID | None = None,
        district: str | None = None,
    ) -> Self:
        return cls(
            event_id=event_id or uuid4(),
            event_type=payload.event_type,
            source=source,
            ts=require_aware(ts),
            correlation_id=correlation_id,
            district=district,
            payload=payload.model_dump(mode="json"),
        )

    def typed_payload(self) -> EventPayload:
        return get_payload_type(self.event_type).model_validate(self.payload)


# --------------------------------------------------------------------------- Core payloads


@register_event("field.state_changed")
class FieldStateChanged(EventPayload):
    field_id: UUID
    previous: FieldState | None
    new: FieldState
    confidence: Confidence
    evidence: list[str] = Field(default_factory=list)


@register_event("field.burn_detected")
class BurnDetected(EventPayload):
    field_id: UUID
    detected_at: datetime
    source: Literal["firms", "sentinel", "farmer_report", "simulation"]
    confidence: Confidence


@register_event("plan.replan_triggered")
class ReplanTriggered(EventPayload):
    district: str
    reason: ReplanReason
    details: dict[str, str] = Field(default_factory=dict)


@register_event("plan.created")
class PlanCreated(EventPayload):
    plan_id: UUID
    district: str
    strategy: str
    fields_assigned: int
    fields_unassigned: int


@register_event("machine.breakdown")
class MachineBreakdown(EventPayload):
    machine_id: UUID
    expected_repair_days: float


@register_event("approval.requested")
class ApprovalRequested(EventPayload):
    approval_id: UUID
    kind: str
    subject_id: UUID
    reason: str
    confidence: Confidence | None = None


@register_event("approval.resolved")
class ApprovalResolved(EventPayload):
    approval_id: UUID
    status: ApprovalStatus
    decided_by_role: str


@register_event("policy.violation")
class PolicyViolationDetected(EventPayload):
    rule_id: str
    severity: Literal["info", "warning", "blocking"]
    action_ref: str
    detail: str


# --------------------------------------------------------------------------- Dialogue payloads


@register_event("farmer.inbound_message")
class FarmerInboundMessage(EventPayload):
    farmer_id: UUID
    conversation_id: UUID
    channel: Channel
    language: Language
    message_text: str
    audio_uri: str | None = None
    detected_intent: str | None = None


@register_event("farmer.outbound_message")
class FarmerOutboundMessage(EventPayload):
    farmer_id: UUID
    conversation_id: UUID
    channel: Channel
    language: Language
    message_text: str
    audio_uri: str | None = None


@register_event("booking.requested")
class BookingRequested(EventPayload):
    booking_id: UUID
    farmer_id: UUID
    field_id: UUID
    service_type: ServiceType
    machine_type: MachineType | None = None
    area_acres: float
    target_date: str


@register_event("pricing.tariff_quote_generated")
class TariffQuoteGenerated(EventPayload):
    quote_id: UUID
    farmer_id: UUID
    field_id: UUID
    service_type: ServiceType
    base_rate_inr: float
    subsidy_discount_inr: float
    net_price_inr: float
    is_concessional: bool


@register_event("negotiation.offer_submitted")
class NegotiationOfferSubmitted(EventPayload):
    session_id: UUID
    buyer_id: UUID
    round_number: int
    offered_price_per_tonne_inr: float
    tonnes: float
    delivery_term: str


@register_event("negotiation.concluded")
class NegotiationConcluded(EventPayload):
    session_id: UUID
    buyer_id: UUID
    agreed: bool
    final_price_per_tonne_inr: float | None = None
    tonnes_agreed: float | None = None
    contract_id: UUID | None = None


@register_event("farmer.escalation_triggered")
class HumanEscalationTriggered(EventPayload):
    escalation_id: UUID
    farmer_id: UUID
    conversation_id: UUID
    reason: str
    urgency: Literal["low", "medium", "critical"] = "medium"
    detected_intent: str | None = None
    farmer_quote: str | None = None


# --------------------------------------------------------------------------- buses

Handler = Callable[[Event], Awaitable[None]]
_dispatch_depth: ContextVar[int] = ContextVar("stubbleos_dispatch_depth", default=0)


@dataclass(frozen=True)
class DeadLetter:
    event: Event
    handler: str
    error: str


@dataclass
class _Sub:
    sub_id: int
    pattern: str
    handler: Handler


class Subscription:
    def __init__(self, bus: EventBus, sub_id: int) -> None:
        self._bus = bus
        self._sub_id = sub_id

    def cancel(self) -> None:
        self._bus._unsubscribe(self._sub_id)


class EventBus(ABC):
    def __init__(
        self,
        *,
        clock: Clock | None = None,
        id_factory: IdFactory = uuid4,
        raise_on_handler_error: bool = False,
    ) -> None:
        self._clock: Clock = clock or SystemClock()
        self._id_factory = id_factory
        self._subs: list[_Sub] = []
        self._next_sub_id = 0
        self.raise_on_handler_error = raise_on_handler_error
        self.dead_letters: list[DeadLetter] = []

    @abstractmethod
    async def publish(self, event: Event) -> None: ...

    def subscribe(self, pattern: str, handler: Handler) -> Subscription:
        """``pattern`` is an fnmatch glob over event types, e.g. ``field.*`` or ``*``."""
        self._next_sub_id += 1
        self._subs.append(_Sub(self._next_sub_id, pattern, handler))
        return Subscription(self, self._next_sub_id)

    def _unsubscribe(self, sub_id: int) -> None:
        self._subs = [s for s in self._subs if s.sub_id != sub_id]

    async def emit(
        self,
        payload: EventPayload,
        *,
        source: str,
        correlation_id: UUID | None = None,
        district: str | None = None,
    ) -> Event:
        event = Event.create(
            payload,
            source=source,
            ts=self._clock.now(),
            event_id=self._id_factory(),
            correlation_id=correlation_id,
            district=district,
        )
        await self.publish(event)
        return event

    @staticmethod
    def _validate(event: Event) -> None:
        get_payload_type(event.event_type)  # raises UnknownEventType

    async def _dispatch(self, event: Event) -> None:
        depth = _dispatch_depth.get()
        if depth >= MAX_DISPATCH_DEPTH:
            raise EventBusError(
                f"dispatch depth exceeded {MAX_DISPATCH_DEPTH} (event loop?) at {event.event_type}"
            )
        token = _dispatch_depth.set(depth + 1)
        try:
            for sub in list(self._subs):
                if not fnmatch.fnmatchcase(event.event_type, sub.pattern):
                    continue
                try:
                    await sub.handler(event)
                except EventBusError:
                    raise
                except Exception as exc:
                    name = getattr(sub.handler, "__qualname__", repr(sub.handler))
                    self.dead_letters.append(DeadLetter(event, name, f"{type(exc).__name__}: {exc}"))
                    HANDLER_ERRORS.labels(handler=name).inc()
                    log.error("event_handler_failed", handler=name, event_type=event.event_type)
                    if self.raise_on_handler_error:
                        raise
        finally:
            _dispatch_depth.reset(token)


class InMemoryEventBus(EventBus):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.history: list[Event] = []

    async def publish(self, event: Event) -> None:
        self._validate(event)
        self.history.append(event)
        EVENTS_PUBLISHED.labels(event_type=event.event_type).inc()
        await self._dispatch(event)

    def of_type(self, event_type: str) -> list[Event]:
        return [e for e in self.history if e.event_type == event_type]


class RedisEventBus(EventBus):
    """Cross-process bus over Redis pub/sub. Call ``start()`` to begin receiving.

    Publishing does not dispatch locally: a process sees its own events only through its own
    listener, so every process observes the same ordering Redis gives it. UNVERIFIED in the
    Local sandbox (no Redis available); covered by tests/integration/test_redis_bus.py when
    ``STUBBLEOS_REDIS_URL`` is reachable.
    """

    CHANNEL_PREFIX = "stubbleos:events:"

    def __init__(self, redis_url: str, *, client: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if client is None:
            import redis.asyncio as aioredis

            client = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
        self._redis: Any = client
        self._pubsub: Any | None = None
        self._listener: asyncio.Task[None] | None = None

    async def publish(self, event: Event) -> None:
        self._validate(event)
        await self._redis.publish(self.CHANNEL_PREFIX + event.event_type, event.model_dump_json())
        EVENTS_PUBLISHED.labels(event_type=event.event_type).inc()

    async def start(self) -> None:
        if self._listener is not None:
            return
        self._pubsub = self._redis.pubsub()
        await self._pubsub.psubscribe(self.CHANNEL_PREFIX + "*")
        self._listener = asyncio.create_task(self._listen(self._pubsub))

    async def _listen(self, pubsub: Any) -> None:
        async for message in pubsub.listen():
            if message.get("type") != "pmessage":
                continue
            try:
                event = Event.model_validate_json(message["data"])
                self._validate(event)
            except (ValidationError, UnknownEventType):
                log.warning("redis_bus_dropped_invalid_event")
                continue
            await self._dispatch(event)

    async def stop(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
            self._listener = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
