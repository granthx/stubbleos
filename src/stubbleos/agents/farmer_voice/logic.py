"""Logic and mock dialogue processing for Farmer Voice agent."""

from __future__ import annotations

from stubbleos.agents.farmer_voice.schemas import (
    FarmerVoiceInput,
    FarmerVoiceOutput,
)
from stubbleos.core.types import Language
from stubbleos.llm.base import LLMClient, LLMRequest


async def process_voice_interaction(
    input_data: FarmerVoiceInput,
    llm: LLMClient | None = None,
) -> FarmerVoiceOutput:
    """Mock conversational processing for farmer outreach."""
    text_lower = input_data.inbound_text.lower()

    if "booking" in text_lower or "machine" in text_lower or "seeder" in text_lower:
        intent = "book_machine"
        default_reply = "ਤੁਹਾਡੀ ਮਸ਼ੀਨ ਬੁਕਿੰਗ ਬੇਨਤੀ ਦਰਜ ਕਰ ਲਈ ਗਈ ਹੈ। (Your machine request is recorded.)"
    elif "price" in text_lower or "rate" in text_lower:
        intent = "query_price"
        default_reply = "ਮੌਜੂਦਾ ਬੇਲਿੰਗ ਦਰ ₹1800 ਪ੍ਰਤੀ ਟਨ ਹੈ। (Current rate is ₹1800 per tonne.)"
    else:
        intent = "general_inquiry"
        default_reply = "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ, ਅਸੀਂ ਪਰਾਲੀ ਪ੍ਰਬੰਧਨ ਵਿੱਚ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦੇ ਹਾਂ? (How can we assist with stubble management?)"

    if llm is not None:
        try:
            req = LLMRequest.simple(
                user_text=f"Respond courteously to farmer inquiry: {input_data.inbound_text}",
                purpose="farmer_voice_response",
                max_tokens=128,
            )
            res = await llm.generate(req)
            reply = res.text.strip()
        except Exception:
            reply = default_reply
    else:
        reply = default_reply

    return FarmerVoiceOutput(
        reply_text=reply,
        language=input_data.language or Language.PUNJABI,
        detected_intent=intent,
        requires_human_escalation=False,
    )
