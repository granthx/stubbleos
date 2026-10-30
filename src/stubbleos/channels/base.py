"""Base interface for all communication channels."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from stubbleos.channels.models import (
    InboundMessage,
    MessageDeliveryResult,
    OutboundMessage,
)
from stubbleos.core.types import Channel


class BaseChannel(ABC):
    """Abstract communication channel adapter."""

    @property
    @abstractmethod
    def channel_type(self) -> Channel:
        """The channel enum supported by this adapter."""
        ...

    @abstractmethod
    async def send_message(self, message: OutboundMessage) -> MessageDeliveryResult:
        """Deliver an outbound message to a recipient."""
        ...

    @abstractmethod
    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage:
        """Parse raw vendor webhook payload into normalized InboundMessage."""
        ...

    def validate_recipient(self, recipient: str) -> bool:
        """Validate recipient identifier format (e.g. phone number or mock ID)."""
        return len(recipient.strip()) > 0
