"""Mock in-memory channel for tests and deterministic simulation."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from stubbleos.channels.base import BaseChannel
from stubbleos.channels.models import (
    InboundMessage,
    MessageDeliveryResult,
    OutboundMessage,
)
from stubbleos.core.clock import Clock, SystemClock
from stubbleos.core.types import Channel, Language


class MockChannel(BaseChannel):
    """In-memory channel recording dispatched messages and simulating replies."""

    def __init__(self, clock: Clock | None = None, fail_next: bool = False) -> None:
        self.clock = clock or SystemClock()
        self.outbox: list[OutboundMessage] = []
        self.fail_next = fail_next

    @property
    def channel_type(self) -> Channel:
        return Channel.MOCK

    async def send_message(self, message: OutboundMessage) -> MessageDeliveryResult:
        now = self.clock.now()
        if self.fail_next:
            self.fail_next = False
            return MessageDeliveryResult(
                message_id=message.message_id,
                channel=Channel.MOCK,
                recipient_id=message.recipient_id,
                success=False,
                status="failed",
                timestamp=now,
                error="Simulated network failure",
            )
        self.outbox.append(message)
        return MessageDeliveryResult(
            message_id=message.message_id,
            channel=Channel.MOCK,
            recipient_id=message.recipient_id,
            success=True,
            status="delivered",
            timestamp=now,
        )

    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage:
        lang_str = payload.get("language", "pa")
        try:
            language = Language(lang_str)
        except ValueError:
            language = Language.PUNJABI

        return InboundMessage(
            message_id=payload.get("message_id", uuid4()),
            sender_id=payload.get("sender_id", "mock_sender"),
            channel=Channel.MOCK,
            language=language,
            text=payload.get("text", ""),
            audio_uri=payload.get("audio_uri"),
            timestamp=self.clock.now(),
            raw_payload=payload,
        )

    def clear(self) -> None:
        self.outbox.clear()
