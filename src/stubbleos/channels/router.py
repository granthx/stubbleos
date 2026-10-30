"""Channel routing, consent verification, and PII boundary enforcement."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from stubbleos.channels.base import BaseChannel
from stubbleos.channels.mock import MockChannel
from stubbleos.channels.models import (
    InboundMessage,
    MessageDeliveryResult,
    OutboundMessage,
)
from stubbleos.core.clock import IST, Clock, SystemClock
from stubbleos.core.events import EventBus, FarmerInboundMessage, FarmerOutboundMessage
from stubbleos.core.logging import get_logger
from stubbleos.core.privacy import Pseudonymizer, redact_text
from stubbleos.core.types import Channel, ConsentPurpose
from stubbleos.data.repositories import ConsentRepository

log = get_logger(__name__)


class ChannelRouter:
    """Coordinates channel adapters, verifies consent, and isolates PII."""

    def __init__(
        self,
        channels: dict[Channel, BaseChannel] | None = None,
        consent_repo: ConsentRepository | None = None,
        event_bus: EventBus | None = None,
        clock: Clock | None = None,
        pseudonymizer: Pseudonymizer | None = None,
        enforce_quiet_hours: bool = True,
    ) -> None:
        self.clock = clock or SystemClock()
        self.consent_repo = consent_repo
        self.event_bus = event_bus
        self.pseudonymizer = pseudonymizer or Pseudonymizer(salt="stubbleos_salt_router")
        self.enforce_quiet_hours = enforce_quiet_hours

        # Default registry with mock fallback
        self._channels: dict[Channel, BaseChannel] = (
            channels if channels is not None else {Channel.MOCK: MockChannel(clock=self.clock)}
        )

    def register_channel(self, channel: BaseChannel) -> None:
        self._channels[channel.channel_type] = channel

    def get_channel(self, channel_type: Channel) -> BaseChannel:
        if channel_type in self._channels:
            return self._channels[channel_type]
        if Channel.MOCK in self._channels:
            return self._channels[Channel.MOCK]
        raise ValueError(f"No adapter registered for channel {channel_type}")

    def is_quiet_hours(self, at: datetime) -> bool:
        """Quiet hours between 21:00 and 07:00 local time (IST)."""
        ist_time = at.astimezone(IST)
        hour = ist_time.hour
        return hour >= 21 or hour < 7

    async def handle_inbound(
        self,
        channel_type: Channel,
        payload: dict[str, Any],
        farmer_id: UUID | None = None,
        conversation_id: UUID | None = None,
        district: str = "sangrur",
    ) -> InboundMessage:
        """Parses vendor webhook, scrubs PII for events, and dispatches event."""
        adapter = self.get_channel(channel_type)
        inbound = adapter.parse_inbound(payload)

        if self.event_bus is not None and farmer_id is not None and conversation_id is not None:
            # Emit event with redacted text for safe audit / analytics
            safe_text = redact_text(inbound.text)
            await self.event_bus.emit(
                FarmerInboundMessage(
                    farmer_id=farmer_id,
                    conversation_id=conversation_id,
                    channel=channel_type,
                    language=inbound.language,
                    message_text=safe_text,
                    audio_uri=inbound.audio_uri,
                    detected_intent=None,
                ),
                source="channel_router",
                district=district,
                correlation_id=conversation_id,
            )

        return inbound

    async def dispatch_outbound(
        self,
        message: OutboundMessage,
        farmer_id: UUID | None = None,
        conversation_id: UUID | None = None,
        district: str = "sangrur",
        purpose: ConsentPurpose = ConsentPurpose.OUTREACH,
    ) -> MessageDeliveryResult:
        """Validates consent and quiet hours, then sends via adapter."""
        now = self.clock.now()

        # 1. Quiet hours check (critical messages bypass quiet hours)
        if self.enforce_quiet_hours and message.priority == "normal" and self.is_quiet_hours(now):
            return MessageDeliveryResult(
                message_id=message.message_id,
                channel=message.channel,
                recipient_id=message.recipient_id,
                success=False,
                status="quiet_hours_delayed",
                timestamp=now,
                error="Message delayed due to quiet hours policy (21:00 - 07:00 IST)",
            )

        # 2. Consent verification
        if self.consent_repo is not None and farmer_id is not None:
            has_consent = self.consent_repo.has_valid_consent(
                farmer_id=farmer_id,
                purpose=purpose,
                channel=message.channel,
                at=now,
            )
            if not has_consent:
                log.warning(
                    "outbound_dispatch_blocked_no_consent",
                    farmer_id=str(farmer_id),
                    channel=message.channel.value,
                    purpose=purpose.value,
                )
                return MessageDeliveryResult(
                    message_id=message.message_id,
                    channel=message.channel,
                    recipient_id=message.recipient_id,
                    success=False,
                    status="blocked_no_consent",
                    timestamp=now,
                    error=f"No valid consent for purpose '{purpose.value}' on channel '{message.channel.value}'",
                )

        # 3. Deliver via channel adapter
        adapter = self.get_channel(message.channel)
        result = await adapter.send_message(message)

        # 4. Emit event bus event if delivered successfully
        if (
            result.success
            and self.event_bus is not None
            and farmer_id is not None
            and conversation_id is not None
        ):
            safe_text = redact_text(message.text)
            await self.event_bus.emit(
                FarmerOutboundMessage(
                    farmer_id=farmer_id,
                    conversation_id=conversation_id,
                    channel=message.channel,
                    language=message.language,
                    message_text=safe_text,
                    audio_uri=message.audio_uri,
                ),
                source="channel_router",
                district=district,
                correlation_id=conversation_id,
            )

        return result
