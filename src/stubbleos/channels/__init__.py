"""Messaging channels subsystem: Base interfaces, WhatsApp, IVR, Mock, and ChannelRouter."""

from stubbleos.channels.base import BaseChannel
from stubbleos.channels.ivr import IVRChannel
from stubbleos.channels.mock import MockChannel
from stubbleos.channels.models import (
    InboundMessage,
    MessageDeliveryResult,
    OutboundMessage,
)
from stubbleos.channels.router import ChannelRouter
from stubbleos.channels.whatsapp import WhatsAppChannel

__all__ = [
    "BaseChannel",
    "ChannelRouter",
    "IVRChannel",
    "InboundMessage",
    "MessageDeliveryResult",
    "MockChannel",
    "OutboundMessage",
    "WhatsAppChannel",
]
