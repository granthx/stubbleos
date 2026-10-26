from uuid import uuid4

import pytest

from stubbleos.core.clock import SimClock
from stubbleos.core.events import (
    Event,
    EventBusError,
    FieldStateChanged,
    InMemoryEventBus,
    ReplanTriggered,
    UnknownEventType,
)
from stubbleos.core.ids import SeededUUIDFactory
from stubbleos.core.types import FieldState, ReplanReason


def fsc() -> FieldStateChanged:
    return FieldStateChanged(field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.8)


async def test_delivery_order_and_patterns(bus: InMemoryEventBus) -> None:
    seen: list[str] = []

    async def a(e: Event) -> None:
        seen.append(f"a:{e.event_type}")

    async def b(e: Event) -> None:
        seen.append(f"b:{e.event_type}")

    bus.subscribe("field.*", a)
    bus.subscribe("*", b)
    await bus.emit(fsc(), source="t")
    await bus.emit(ReplanTriggered(district="d", reason=ReplanReason.DAILY), source="t")
    assert seen == ["a:field.state_changed", "b:field.state_changed", "b:plan.replan_triggered"]


async def test_handler_error_is_isolated_and_recorded(bus: InMemoryEventBus) -> None:
    got: list[Event] = []

    async def bad(_: Event) -> None:
        raise RuntimeError("kaput")

    async def good(e: Event) -> None:
        got.append(e)

    bus.subscribe("*", bad)
    bus.subscribe("*", good)
    await bus.emit(fsc(), source="t")
    assert len(got) == 1
    assert len(bus.dead_letters) == 1
    assert "kaput" in bus.dead_letters[0].error


async def test_raise_on_handler_error(clock: SimClock) -> None:
    strict = InMemoryEventBus(clock=clock, raise_on_handler_error=True)

    async def bad(_: Event) -> None:
        raise RuntimeError("kaput")

    strict.subscribe("*", bad)
    with pytest.raises(RuntimeError):
        await strict.emit(fsc(), source="t")


async def test_cancel_subscription(bus: InMemoryEventBus) -> None:
    got: list[Event] = []

    async def h(e: Event) -> None:
        got.append(e)

    sub = bus.subscribe("*", h)
    await bus.emit(fsc(), source="t")
    sub.cancel()
    await bus.emit(fsc(), source="t")
    assert len(got) == 1


async def test_unknown_event_rejected_on_publish(bus: InMemoryEventBus, clock: SimClock) -> None:
    bad = Event(event_id=uuid4(), event_type="made.up", source="t", ts=clock.now(), payload={})
    with pytest.raises(UnknownEventType):
        await bus.publish(bad)
    assert bus.history == []


async def test_runaway_loop_is_stopped(bus: InMemoryEventBus) -> None:
    async def loop(_: Event) -> None:
        await bus.emit(fsc(), source="loop")

    bus.subscribe("field.*", loop)
    with pytest.raises(EventBusError):
        await bus.emit(fsc(), source="t")


async def test_emit_stamps_clock_and_is_deterministic(clock: SimClock) -> None:
    p = fsc()
    b1 = InMemoryEventBus(clock=clock, id_factory=SeededUUIDFactory(7))
    b2 = InMemoryEventBus(clock=clock, id_factory=SeededUUIDFactory(7))
    e1 = await b1.emit(p, source="t", district="ludhiana")
    e2 = await b2.emit(p, source="t", district="ludhiana")
    assert e1 == e2
    assert e1.ts == clock.now()
    assert e1.district == "ludhiana"
