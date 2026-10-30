"""Unit tests for Phase 6 edge cases and failure modes."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from stubbleos.agents.farmer_voice.logic import (
    process_voice_interaction,
)
from stubbleos.agents.farmer_voice.schemas import FarmerVoiceInput
from stubbleos.agents.pricing_negotiation.schemas import BiomassOffer, PricingInput
from stubbleos.channels.models import OutboundMessage
from stubbleos.channels.router import ChannelRouter
from stubbleos.channels.whatsapp import WhatsAppChannel
from stubbleos.core.clock import IST, SimClock
from stubbleos.core.events import InMemoryEventBus
from stubbleos.core.types import Channel, LandholdingClass, ServiceType


@pytest.mark.asyncio
async def test_invalid_phone_number_delivery_failure() -> None:
    wa = WhatsAppChannel()

    # Invalid phone number (letters, too short)
    msg = OutboundMessage(
        recipient_id="invalid-phone-123",
        channel=Channel.WHATSAPP,
        text="Hello",
    )
    res = await wa.send_message(msg)
    assert res.success is False
    assert res.status == "failed"
    assert "Invalid WhatsApp phone number" in (res.error or "")


@pytest.mark.asyncio
async def test_empty_or_whitespace_voice_input() -> None:
    f_id = uuid.uuid4()
    inp = FarmerVoiceInput(
        farmer_id=f_id,
        inbound_text="    ",
    )
    out = await process_voice_interaction(inp)
    assert out.detected_intent == "general_inquiry"
    assert len(out.reply_text) > 0


def test_pricing_validation_errors() -> None:
    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()

    # Zero or negative area acres
    with pytest.raises(ValidationError):
        PricingInput(
            farmer_id=f_id,
            field_id=fld_id,
            landholding_class=LandholdingClass.SMALL,
            service_type=ServiceType.IN_SITU_SOWING,
            area_acres=0.0,
        )

    # Negative price per tonne
    with pytest.raises(ValidationError):
        BiomassOffer(
            buyer_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            proposed_price_per_tonne_inr=-500.0,
            tonnes=100.0,
        )


@pytest.mark.asyncio
async def test_channel_router_unregistered_channel() -> None:
    router = ChannelRouter(channels={})

    # Asking for an unregistered channel without fallback raises ValueError
    with pytest.raises(ValueError, match="No adapter registered"):
        router.get_channel(Channel.WHATSAPP)


@pytest.mark.asyncio
async def test_channel_pii_redaction_in_event_bus() -> None:
    clock = SimClock(start=datetime(2026, 10, 30, 14, 0, tzinfo=IST))
    event_bus = InMemoryEventBus(clock=clock)
    received_events: list[str] = []

    async def audit_listener(event) -> None:
        received_events.append(event.payload.get("message_text", ""))

    event_bus.subscribe("farmer.inbound_message", audit_listener)

    router = ChannelRouter(
        event_bus=event_bus,
        clock=clock,
        enforce_quiet_hours=False,
    )

    # Inbound message containing sensitive phone number and Aadhaar number
    payload = {
        "sender_id": "+919876543210",
        "text": "Call me at +919876543210 and my Aadhaar is 2345 6789 0123",
    }

    f_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    await router.handle_inbound(
        channel_type=Channel.MOCK,
        payload=payload,
        farmer_id=f_id,
        conversation_id=conv_id,
    )

    assert len(received_events) == 1
    event_text = received_events[0]

    # Verify that the event bus received REDACTED content
    assert "+919876543210" not in event_text
    assert "2345 6789 0123" not in event_text
    assert "[REDACTED]" in event_text
