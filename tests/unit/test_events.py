from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from stubbleos.core.events import (
    Event,
    EventPayload,
    FieldStateChanged,
    UnknownEventType,
    get_payload_type,
    register_event,
    registered_event_types,
)
from stubbleos.core.types import FieldState

TS = datetime(2026, 10, 20, tzinfo=UTC)


def test_roundtrip_through_json() -> None:
    payload = FieldStateChanged(
        field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.9, evidence=["fixture"]
    )
    event = Event.create(payload, source="field_monitor", ts=TS)
    restored = Event.model_validate_json(event.model_dump_json())
    assert restored == event
    assert restored.typed_payload() == payload


def test_unknown_type_raises() -> None:
    event = Event(event_id=uuid4(), event_type="nope.nothing", source="x", ts=TS, payload={})
    with pytest.raises(UnknownEventType):
        event.typed_payload()


def test_payload_validation_is_strict() -> None:
    with pytest.raises(ValidationError):
        FieldStateChanged(field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=1.5)
    with pytest.raises(ValidationError):
        FieldStateChanged(  # type: ignore[call-arg]
            field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.5, surprise=1
        )


def test_naive_timestamp_rejected() -> None:
    p = FieldStateChanged(field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.5)
    with pytest.raises(ValueError, match="naive datetime not allowed"):
        Event.create(p, source="x", ts=datetime(2026, 1, 1))


def test_duplicate_registration_conflicts() -> None:
    with pytest.raises(ValueError, match="already registered"):

        @register_event("field.state_changed")
        class Other(EventPayload):
            x: int = 0


def test_registry_contents() -> None:
    assert "field.state_changed" in registered_event_types()
    assert get_payload_type("approval.requested").event_type == "approval.requested"
