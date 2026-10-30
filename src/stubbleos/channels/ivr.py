"""Interactive Voice Response (IVR) and telephony channel adapter."""

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


class IVRChannel(BaseChannel):
    """Telephony IVR channel adapter for automated vernacular voice calls."""

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock or SystemClock()
        self.active_calls: dict[str, dict[str, Any]] = {}
        self.call_history: list[dict[str, Any]] = []

    @property
    def channel_type(self) -> Channel:
        return Channel.VOICE

    def validate_recipient(self, recipient: str) -> bool:
        clean = recipient.strip().replace(" ", "").replace("-", "")
        return bool(_E164_PHONE.match(clean))

    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage:
        """Parses IVR webhook payload (e.g. DTMF response or ASR audio transcript)."""
        now = self.clock.now()
        sender = str(payload.get("From") or payload.get("caller_id") or payload.get("sender_id") or "unknown")

        # DTMF or spoken text
        digits = payload.get("Digits")
        speech_result = payload.get("SpeechResult") or payload.get("transcript")
        audio_url = payload.get("RecordingUrl") or payload.get("audio_uri")

        text = ""
        if digits is not None:
            text = f"DTMF:{digits}"
        elif speech_result:
            text = str(speech_result)

        lang_code = payload.get("Language") or payload.get("language", "pa")
        try:
            language = Language(lang_code)
        except ValueError:
            language = Language.PUNJABI

        return InboundMessage(
            message_id=uuid4(),
            sender_id=sender,
            channel=Channel.VOICE,
            language=language,
            text=text,
            audio_uri=str(audio_url) if audio_url else None,
            timestamp=now,
            raw_payload=payload,
        )

    async def send_message(self, message: OutboundMessage) -> MessageDeliveryResult:
        """Dispatches an outbound IVR call or plays a voice prompt."""
        now = self.clock.now()
        if not self.validate_recipient(message.recipient_id):
            return MessageDeliveryResult(
                message_id=message.message_id,
                channel=Channel.VOICE,
                recipient_id=message.recipient_id,
                success=False,
                status="failed",
                timestamp=now,
                error=f"Invalid phone number for IVR call: {message.recipient_id}",
            )

        call_id = f"call_{uuid4().hex[:12]}"
        call_record = {
            "call_id": call_id,
            "recipient": message.recipient_id,
            "prompt_text": message.text,
            "audio_uri": message.audio_uri,
            "language": message.language.value,
            "status": "answered",
            "timestamp": now.isoformat(),
        }
        self.active_calls[call_id] = call_record
        self.call_history.append(call_record)

        return MessageDeliveryResult(
            message_id=message.message_id,
            channel=Channel.VOICE,
            recipient_id=message.recipient_id,
            success=True,
            status="delivered",
            timestamp=now,
        )
