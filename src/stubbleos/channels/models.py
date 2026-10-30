"""Typed models for channel messaging (WhatsApp, IVR, Mock)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field

from stubbleos.core.clock import require_aware
from stubbleos.core.types import Channel, Language, StrictModel


class InboundMessage(StrictModel):
    """Normalized inbound message from any channel."""

    message_id: UUID = Field(default_factory=uuid4)
    sender_id: str
    channel: Channel
    language: Language = Language.PUNJABI
    text: str = ""
    audio_uri: str | None = None
    timestamp: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        require_aware(self.timestamp)


class OutboundMessage(StrictModel):
    """Outbound message to be delivered to a recipient."""

    message_id: UUID = Field(default_factory=uuid4)
    recipient_id: str
    channel: Channel
    language: Language = Language.PUNJABI
    text: str
    audio_uri: str | None = None
    template_name: str | None = None
    template_params: dict[str, str] = Field(default_factory=dict)
    quick_replies: list[str] = Field(default_factory=list)
    priority: Literal["normal", "urgent", "critical"] = "normal"


class MessageDeliveryResult(StrictModel):
    """Result of attempting to dispatch an outbound message."""

    message_id: UUID
    channel: Channel
    recipient_id: str
    success: bool
    status: Literal["delivered", "queued", "failed", "blocked_no_consent", "quiet_hours_delayed"]
    timestamp: datetime
    error: str | None = None

    def model_post_init(self, __context: Any) -> None:
        require_aware(self.timestamp)
