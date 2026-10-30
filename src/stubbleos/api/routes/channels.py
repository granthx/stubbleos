"""Channels Webhook REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from stubbleos.channels.ivr import IVRChannel
from stubbleos.channels.whatsapp import WhatsAppChannel
from stubbleos.core.types import Channel

router = APIRouter(prefix="/channels", tags=["Channels"])

wa_adapter = WhatsAppChannel()
ivr_adapter = IVRChannel()


@router.post("/webhook/{channel}")
async def receive_channel_webhook(channel: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Ingests inbound WhatsApp or IVR webhooks."""
    ch_lower = channel.lower()
    if ch_lower == Channel.WHATSAPP.value:
        inbound = wa_adapter.parse_inbound(payload)
        return {
            "status": "received",
            "channel": Channel.WHATSAPP.value,
            "message_id": str(inbound.message_id),
            "sender_id": inbound.sender_id,
            "text": inbound.text,
        }
    elif ch_lower == Channel.VOICE.value:
        inbound = ivr_adapter.parse_inbound(payload)
        return {
            "status": "received",
            "channel": Channel.VOICE.value,
            "message_id": str(inbound.message_id),
            "sender_id": inbound.sender_id,
            "text": inbound.text,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported webhook channel: {channel}",
        )
