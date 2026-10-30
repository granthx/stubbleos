"""Unit tests for Phase 6 Messaging Channels & Router."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from stubbleos.channels.ivr import IVRChannel
from stubbleos.channels.mock import MockChannel
from stubbleos.channels.models import OutboundMessage
from stubbleos.channels.router import ChannelRouter
from stubbleos.channels.whatsapp import WhatsAppChannel
from stubbleos.core.clock import IST, SimClock
from stubbleos.core.events import InMemoryEventBus
from stubbleos.core.types import Channel, ConsentPurpose


@pytest.mark.asyncio
async def test_whatsapp_webhook_parsing_and_sending() -> None:
    wa = WhatsAppChannel()

    # Inbound Meta Cloud API text message webhook
    meta_webhook = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "type": "text",
                                    "text": {"body": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    inbound = wa.parse_inbound(meta_webhook)
    assert inbound.sender_id == "919876543210"
    assert inbound.text == "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ"
    assert inbound.channel == Channel.WHATSAPP

    # Outbound WhatsApp message delivery
    msg = OutboundMessage(
        recipient_id="+919876543210",
        channel=Channel.WHATSAPP,
        text="ਤੁਹਾਡੀ ਮਸ਼ੀਨ ਬੁਕਿੰਗ ਦੀ ਪੁਸ਼ਟੀ ਹੋ ਗਈ ਹੈ।",
        quick_replies=["ਹਾਂ", "ਨਹੀਂ"],
    )
    res = await wa.send_message(msg)
    assert res.success is True
    assert res.status == "delivered"
    assert len(wa.sent_payloads) == 1
    assert wa.sent_payloads[0]["to"] == "+919876543210"


@pytest.mark.asyncio
async def test_ivr_call_dispatch_and_dtmf() -> None:
    ivr = IVRChannel()

    # Outbound call
    msg = OutboundMessage(
        recipient_id="+919876543210",
        channel=Channel.VOICE,
        text="ਮਸ਼ੀਨ ਬੁਕਿੰਗ ਲਈ 1 ਦਬਾਓ, ਰੱਦ ਕਰਨ ਲਈ 2 ਦਬਾਓ।",
        audio_uri="s3://stubbleos-audio/ivr_prompt_01.wav",
    )
    res = await ivr.send_message(msg)
    assert res.success is True
    assert len(ivr.call_history) == 1

    # Inbound DTMF digit webhook
    dtmf_payload = {
        "From": "+919876543210",
        "Digits": "1",
    }
    inbound = ivr.parse_inbound(dtmf_payload)
    assert inbound.text == "DTMF:1"
    assert inbound.channel == Channel.VOICE


@pytest.mark.asyncio
async def test_channel_router_consent_enforcement() -> None:
    clock = SimClock(start=datetime(2026, 10, 30, 11, 0, tzinfo=IST))  # 11:00 AM (daytime)
    event_bus = InMemoryEventBus(clock=clock)
    mock_ch = MockChannel(clock=clock)

    # Class mimicking ConsentRepository for unit testing
    class FakeConsentRepo:
        def __init__(self, consents: set[tuple[uuid.UUID, ConsentPurpose, Channel]] | None = None) -> None:
            self.consents = consents or set()

        def has_valid_consent(
            self, farmer_id: uuid.UUID, purpose: ConsentPurpose, channel: Channel, at: datetime
        ) -> bool:
            return (farmer_id, purpose, channel) in self.consents

    f_consented = uuid.uuid4()
    f_unconsented = uuid.uuid4()

    consent_repo = FakeConsentRepo(consents={(f_consented, ConsentPurpose.OUTREACH, Channel.MOCK)})

    router = ChannelRouter(
        channels={Channel.MOCK: mock_ch},
        consent_repo=consent_repo,  # type: ignore[arg-type]
        event_bus=event_bus,
        clock=clock,
    )

    # 1. Allowed dispatch for consented farmer
    msg_allowed = OutboundMessage(
        recipient_id="f_consented_recipient",
        channel=Channel.MOCK,
        text="Machine arrives today at 2 PM",
    )
    res1 = await router.dispatch_outbound(
        msg_allowed,
        farmer_id=f_consented,
        conversation_id=uuid.uuid4(),
        purpose=ConsentPurpose.OUTREACH,
    )
    assert res1.success is True
    assert res1.status == "delivered"

    # 2. Blocked dispatch for unconsented farmer
    msg_blocked = OutboundMessage(
        recipient_id="f_unconsented_recipient",
        channel=Channel.MOCK,
        text="Special machinery discount offer",
    )
    res2 = await router.dispatch_outbound(
        msg_blocked,
        farmer_id=f_unconsented,
        conversation_id=uuid.uuid4(),
        purpose=ConsentPurpose.OUTREACH,
    )
    assert res2.success is False
    assert res2.status == "blocked_no_consent"


@pytest.mark.asyncio
async def test_channel_router_quiet_hours_policy() -> None:
    # 23:30 IST is during quiet hours (21:00 - 07:00 IST)
    night_time = datetime(2026, 10, 30, 23, 30, tzinfo=IST)
    clock = SimClock(start=night_time)
    mock_ch = MockChannel(clock=clock)

    router = ChannelRouter(
        channels={Channel.MOCK: mock_ch},
        clock=clock,
        enforce_quiet_hours=True,
    )

    # Normal priority message is delayed during quiet hours
    msg_normal = OutboundMessage(
        recipient_id="test_farmer",
        channel=Channel.MOCK,
        text="Routine weekly update",
        priority="normal",
    )
    res_normal = await router.dispatch_outbound(msg_normal)
    assert res_normal.success is False
    assert res_normal.status == "quiet_hours_delayed"

    # Critical priority message (e.g. fire hazard emergency) bypasses quiet hours
    msg_critical = OutboundMessage(
        recipient_id="test_farmer",
        channel=Channel.MOCK,
        text="EMERGENCY: Urgent harvest fire risk in your sector!",
        priority="critical",
    )
    res_critical = await router.dispatch_outbound(msg_critical)
    assert res_critical.success is True
    assert res_critical.status == "delivered"
