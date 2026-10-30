"""WhatsApp Business API channel adapter."""

from __future__ import annotations

import re
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

_E164_PHONE = re.compile(r"^\+?[1-9]\d{9,14}$")


class WhatsAppChannel(BaseChannel):
    """WhatsApp Cloud / Business API adapter."""

    def __init__(self, clock: Clock | None = None, api_token: str | None = None) -> None:
        self.clock = clock or SystemClock()
        self.api_token = api_token or "mock_wa_token"
        self.sent_payloads: list[dict[str, Any]] = []

    @property
    def channel_type(self) -> Channel:
        return Channel.WHATSAPP

    def validate_recipient(self, recipient: str) -> bool:
        clean = recipient.strip().replace(" ", "").replace("-", "")
        return bool(_E164_PHONE.match(clean))

    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage:
        """Parses Meta WhatsApp webhook payload."""
        now = self.clock.now()
        sender = "unknown"
        text = ""
        audio_uri = None

        # Check Meta Cloud API webhook format: entry -> changes -> value -> messages
        if "entry" in payload:
            try:
                change_val = payload["entry"][0]["changes"][0]["value"]
                msg = change_val["messages"][0]
                sender = msg.get("from", "unknown")
                msg_type = msg.get("type", "text")
                if msg_type == "text":
                    text = msg.get("text", {}).get("body", "")
                elif msg_type == "audio":
                    audio_uri = (
                        msg.get("audio", {}).get("link")
                        or f"whatsapp://media/{msg.get('audio', {}).get('id')}"
                    )
                elif msg_type == "interactive":
                    # Interactive button reply
                    reply = msg.get("interactive", {}).get("button_reply", {})
                    text = reply.get("title", "") or reply.get("id", "")
            except (KeyError, IndexError):
                pass
        else:
            # Flattened / simplified webhook format
            sender = str(payload.get("from") or payload.get("sender_id") or "unknown")
            text = str(payload.get("text") or payload.get("body") or "")
            audio_uri = payload.get("audio_uri")

        # Determine language hint
        lang_code = payload.get("language", "pa")
        try:
            language = Language(lang_code)
        except ValueError:
            language = Language.PUNJABI

        return InboundMessage(
            message_id=uuid4(),
            sender_id=sender,
            channel=Channel.WHATSAPP,
            language=language,
            text=text,
            audio_uri=audio_uri,
            timestamp=now,
            raw_payload=payload,
        )

    async def send_message(self, message: OutboundMessage) -> MessageDeliveryResult:
        now = self.clock.now()
        if not self.validate_recipient(message.recipient_id):
            return MessageDeliveryResult(
                message_id=message.message_id,
                channel=Channel.WHATSAPP,
                recipient_id=message.recipient_id,
                success=False,
                status="failed",
                timestamp=now,
                error=f"Invalid WhatsApp phone number: {message.recipient_id}",
            )

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": message.recipient_id,
        }

        if message.template_name:
            payload["type"] = "template"
            payload["template"] = {
                "name": message.template_name,
                "language": {"code": message.language.value},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": v} for v in message.template_params.values()],
                    }
                ],
            }
        elif message.quick_replies:
            payload["type"] = "interactive"
            payload["interactive"] = {
                "type": "button",
                "body": {"text": message.text},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": f"btn_{i}", "title": label[:20]}}
                        for i, label in enumerate(message.quick_replies[:3])
                    ]
                },
            }
        else:
            payload["type"] = "text"
            payload["text"] = {"body": message.text}

        self.sent_payloads.append(payload)

        return MessageDeliveryResult(
            message_id=message.message_id,
            channel=Channel.WHATSAPP,
            recipient_id=message.recipient_id,
            success=True,
            status="delivered",
            timestamp=now,
        )
