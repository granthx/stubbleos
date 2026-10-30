"""Conversational logic, multilingual intent classification, and slot filling for Farmer Voice."""

from __future__ import annotations

import contextlib
import re

from stubbleos.agents.farmer_voice.schemas import (
    FarmerVoiceBookingDraft,
    FarmerVoiceInput,
    FarmerVoiceOutput,
    FarmerVoiceSlotState,
)
from stubbleos.core.logging import get_logger
from stubbleos.core.types import Language, MachineType
from stubbleos.llm.base import LLMClient, LLMRequest
from stubbleos.llm.prompts import default_registry

log = get_logger(__name__)

_BURN_THREAT_KEYWORDS = [
    "ਅੱਗ",
    "ਸਾੜ",
    "ਸਾੜਾਂਗਾ",
    "ਆਗ",
    "ਜਲਾ",
    "ਜਲਾ ਦੂੰਗਾ",
    "burn",
    "fire",
    "set fire",
    "burning",
    "aag laga",
]

_ACRES_REGEX = re.compile(r"(\d+(?:\.\d+)?)\s*(?:acres?|acre|ਏਕੜ|एकੜ|kille|ਕਿੱਲੇ|ਕਿਲੇ|किला|ਕਿਲਾ)", re.IGNORECASE)
_VILLAGE_REGEX = re.compile(
    r"(?:ਪਿੰਡ|गाँव|village|tehsil|ਤਹਿਸੀਲ)\s+([A-Za-z\u0A00-\u0A7F\u0900-\u097F]+)", re.IGNORECASE
)


def detect_language(text: str, fallback: Language = Language.PUNJABI) -> Language:
    """Infers language from script characters with fallback."""
    # Gurmukhi Unicode block: U+0A00 to U+0A7F
    if any("\u0a00" <= c <= "\u0a7f" for c in text):
        return Language.PUNJABI
    # Devanagari Unicode block: U+0900 to U+097F
    if any("\u0900" <= c <= "\u097f" for c in text):
        return Language.HINDI
    return fallback


def extract_entities(text: str, current_slots: FarmerVoiceSlotState | None = None) -> FarmerVoiceSlotState:
    """Extracts acreage, machine type, village, and confirmation from inbound text."""
    slots = current_slots.model_copy() if current_slots else FarmerVoiceSlotState()
    lower = text.lower()

    # Acreage
    match_acres = _ACRES_REGEX.search(text)
    if match_acres:
        with contextlib.suppress(ValueError):
            slots.area_acres = float(match_acres.group(1))
    elif not slots.area_acres:
        # Bare digit if followed by farm context
        for token in text.split():
            if token.isdigit() and 1 <= int(token) <= 200:
                slots.area_acres = float(token)
                break

    # Machine Type
    if "super" in lower or "ਸੁਪਰ" in lower or "सुपर" in lower:
        slots.machine_type = MachineType.SUPER_SEEDER
    elif "happy" in lower or "ਹੈਪੀ" in lower or "हैप्पी" in lower:
        slots.machine_type = MachineType.HAPPY_SEEDER
    elif "baler" in lower or "ਬੇਲਰ" in lower or "बेलर" in lower:
        slots.machine_type = MachineType.BALER
    elif "rake" in lower or "ਰੇਕ" in lower or "रेक" in lower:
        slots.machine_type = MachineType.RAKE

    # Village
    match_village = _VILLAGE_REGEX.search(text)
    if match_village:
        slots.village = match_village.group(1).strip()
    elif "sangrur" in lower or "ਸੰਗਰੂਰ" in lower:
        slots.village = "Sangrur"
    elif "nabha" in lower or "ਨਾਭਾ" in lower:
        slots.village = "Nabha"
    elif "patiala" in lower or "ਪਟਿਆਲਾ" in lower:
        slots.village = "Patiala"

    # Confirmation
    if any(k in lower for k in ["yes", "ਹਾਂ", "हाँ", "haan", "haaji", "ok", "1", "confirm", "ਮਨਜ਼ੂਰ"]):
        slots.is_confirmed = True

    return slots


def classify_intent(text: str) -> tuple[str, float]:
    """Classifies user intent and returns (intent, confidence)."""
    text_lower = text.lower()

    # Priority 1: Burning threat (critical urgency)
    if any(kw in text_lower for kw in _BURN_THREAT_KEYWORDS):
        return ("threat_burn", 0.99)

    # Priority 2: Confirmation / Acceptance
    if any(k in text_lower for k in ["confirm", "ਮਨਜ਼ੂਰ", "मंजूर", "ਠੀਕ ਹੈ", "ठीक है"]) or text_lower in {
        "yes",
        "haan",
        "ਹਾਂ",
        "हाँ",
        "ok",
        "confirm",
        "1",
        "haaji",
        "ਹਾਂਜੀ",
        "हाँजी",
    }:
        return ("confirm_booking", 0.95)

    # Priority 3: Cancellation
    if any(k in text_lower for k in ["cancel", "ਰੱਦ", "रद्द", "nahi", "ਨਹੀਂ ਚਾਹੀਦਾ", "ਕੈਂਸਲ", "कैंसिल"]):
        return ("cancel_booking", 0.92)

    # Priority 4: Schedule check (check before machine keyword matches)
    if any(
        k in text_lower
        for k in ["status", "schedule", "ਕਦੋਂ", "ਆਵੇਗੀ", "time", "location", "ਸਥਿਤੀ", "स्थिति", "कब", "आएगी"]
    ):
        return ("check_schedule_status", 0.90)

    # Priority 5: Price query
    if any(
        k in text_lower
        for k in ["price", "rate", "ਰੇਟ", "ਦਰ", "ਕੀਮਤ", "cost", "rupees", "ਕਿੰਨੇ", "रेट", "दर", "कीमत", "कितने"]
    ):
        return ("query_price", 0.93)

    # Priority 6: Booking request (multilingual)
    if any(
        k in text_lower
        for k in [
            "booking",
            "machine",
            "ਮਸ਼ੀਨ",
            "seeder",
            "ਸੀਡਰ",
            "baler",
            "ਬੇਲਰ",
            "rent",
            "ਬੁਕਿੰਗ",
            "ਬੁੱਕ",
            "ਸੁਪਰ",
            "ਹੈਪੀ",
            "ਚਾਹੀਦਾ",
            "बुकिंग",
            "मशीन",
            "सीडर",
            "बेलर",
            "सुपर",
            "हैप्पी",
            "चाहिए",
            "किराया",
        ]
    ):
        return ("book_machine", 0.94)

    # Priority 7: Complaint
    if any(k in text_lower for k in ["complaint", "ਸ਼ਿਕਾਇਤ", "शिकायत", "ਖਰਾਬ", "problem", "masla", "خراب"]):
        return ("report_complaint", 0.91)

    return ("general_inquiry", 0.80)


async def process_voice_interaction(
    input_data: FarmerVoiceInput,
    current_slots: FarmerVoiceSlotState | None = None,
    llm: LLMClient | None = None,
) -> FarmerVoiceOutput:
    """Executes multi-turn vernacular dialogue processing."""
    text = input_data.inbound_text.strip()
    language = input_data.language or detect_language(text)

    # 1. Intent classification & Entity extraction
    intent, confidence = classify_intent(text)
    slots = extract_entities(text, current_slots)

    # Continue ongoing booking if slots are present or being answered
    if intent == "general_inquiry" and (
        slots.area_acres is not None
        or slots.machine_type is not None
        or (current_slots is not None and (current_slots.machine_type or current_slots.area_acres))
    ):
        intent = "book_machine"

    requires_human_escalation = False
    escalation_reason = None
    action_requested = None
    booking_draft = None

    # 2. Urgent Threat Handling (Immediate De-escalation & HITL Alert)
    if intent == "threat_burn":
        requires_human_escalation = True
        escalation_reason = "burn_threat_detected"
        action_requested = "escalate_to_human"
        prompt_t = default_registry.get("farmer_voice_burn_threat_deescalation", language=language)
        reply = prompt_t.template

    # 3. Booking Intent with Multi-turn Slot Filling
    elif intent in {"book_machine", "confirm_booking"}:
        if slots.is_confirmed and slots.area_acres and slots.machine_type:
            # Booking confirmed!
            village_name = slots.village or "ਸਥਾਨਕ ਪਿੰਡ (Local village)"
            draft = FarmerVoiceBookingDraft(
                area_acres=slots.area_acres,
                village=village_name,
                machine_type=slots.machine_type,
                target_date="2026-11-01",
                crop_type="paddy",
                estimated_rate_inr=slots.area_acres * 1200.0,
            )
            booking_draft = draft
            action_requested = "submit_booking"
            if language == Language.PUNJABI:
                reply = f"ਧੰਨਵਾਦ ਜੀ! {village_name} ਵਿੱਚ {slots.area_acres} ਏਕੜ ਲਈ {slots.machine_type.value} ਦੀ ਬੁਕਿੰਗ ਸਫਲਤਾਪੂਰਵਕ ਦਰਜ ਕਰ ਲਈ ਗਈ ਹੈ। (Booking confirmed.)"
            elif language == Language.HINDI:
                reply = f"धन्यवाद! {village_name} में {slots.area_acres} एकड़ के लिए {slots.machine_type.value} की बुकिंग सफलतापूर्वक दर्ज कर ली गई है। (Booking confirmed.)"
            else:
                reply = f"Thank you! Your booking for {slots.machine_type.value} on {slots.area_acres} acres in {village_name} is confirmed."

        elif not slots.area_acres:
            # Need area slot
            if language == Language.PUNJABI:
                reply = "ਕਿਰਪਾ ਕਰਕੇ ਦੱਸੋ ਕਿ ਤੁਹਾਡਾ ਕਿੰਨੇ ਏਕੜ ਜਾਂ ਕਿੱਲੇ ਖੇਤ ਹੈ? (How many acres is your field?)"
            elif language == Language.HINDI:
                reply = "कृपया बताएं कि आपका खेत कितने एकड़ है? (How many acres is your field?)"
            else:
                reply = "Please specify how many acres you need the machine for."

        elif not slots.machine_type:
            # Need machine type slot
            if language == Language.PUNJABI:
                reply = "ਤੁਹਾਨੂੰ ਕਿਹੜੀ ਮਸ਼ੀਨ ਚਾਹੀਦੀ ਹੈ: ਸੁਪਰ ਸੀਡਰ (Super Seeder) ਜਾਂ ਬੇਲਰ (Baler)?"
            elif language == Language.HINDI:
                reply = "आपको कौन सी मशीन चाहिए: सुपर सीडर (Super Seeder) या बेलर (Baler)?"
            else:
                reply = "Which machine do you require: Super Seeder or Baler?"

        else:
            # All slots gathered, present confirmation quote
            village_name = slots.village or "ਸਥਾਨਕ ਪਿੰਡ (Local village)"
            est_cost = slots.area_acres * 1200.0
            rendered = default_registry.render(
                "farmer_voice_booking_confirm",
                language=language,
                machine_type=slots.machine_type.value,
                acres=f"{slots.area_acres:.1f}",
                village=village_name,
                date="2026-11-01",
                net_price=f"{est_cost:.0f}",
            )
            reply = rendered.text

    # 4. Price Query
    elif intent == "query_price":
        if language == Language.PUNJABI:
            reply = "ਸੁਪਰ ਸੀਡਰ ਇਨ-ਸੀਟੂ ਬਿਜਾਈ ਦਰ ₹1200 ਪ੍ਰਤੀ ਏਕੜ ਹੈ। ਮੌਜੂਦਾ ਬੇਲਿੰਗ ਦਰ ₹1800 ਪ੍ਰਤੀ ਟਨ ਹੈ। ਛੋਟੇ ਕਿਸਾਨਾਂ ਨੂੰ 25% ਸਬਸਿਡੀ ਉਪਲਬਧ ਹੈ।"
        elif language == Language.HINDI:
            reply = "सुपर सीडर इन-सीटू बुवाई दर ₹1200 प्रति एकड़ है। वर्तमान बेलिंग दर ₹1800 प्रति टन है। छोटे किसानों के लिए 25% सब्सिडी उपलब्ध है।"
        else:
            reply = "Super Seeder rate is ₹1200/acre. Current baling rate is ₹1800 per tonne. Smallholders receive a 25% cooperative subsidy discount."

    # 5. Schedule Status Query
    elif intent == "check_schedule_status":
        if language == Language.PUNJABI:
            reply = (
                "ਤੁਹਾਡੀ ਮਸ਼ੀਨ ਤਹਿ ਕੀਤੇ ਸਮੇਂ ਅਨੁਸਾਰ ਕੱਲ੍ਹ ਸਵੇਰੇ 10:00 ਵਜੇ ਪਹੁੰਚ ਰਹੀ ਹੈ। (Machine arrives tomorrow 10:00 AM.)"
            )
        elif language == Language.HINDI:
            reply = (
                "आपकी मशीन निर्धारित समय पर कल सुबह 10:00 बजे पहुँच रही है। (Machine arrives tomorrow 10:00 AM.)"
            )
        else:
            reply = "Your machine is scheduled for dispatch tomorrow at 10:00 AM."

    # 6. Cancellation
    elif intent == "cancel_booking":
        action_requested = "cancel_booking"
        if language == Language.PUNJABI:
            reply = "ਤੁਹਾਡੀ ਬੁਕਿੰਗ ਰੱਦ ਕਰ ਦਿੱਤੀ ਗਈ ਹੈ। ਜੇ ਦੁਬਾਰਾ ਲੋੜ ਹੋਵੇ ਤਾਂ ਸੰਪਰਕ ਕਰੋ। (Booking cancelled.)"
        elif language == Language.HINDI:
            reply = "आपकी बुकिंग रद्द कर दी गई है। आवश्यकता होने पर पुनः संपर्क करें। (Booking cancelled.)"
        else:
            reply = "Your booking request has been cancelled."

    # 7. General Inquiry / Fallback
    else:
        if language == Language.PUNJABI:
            reply = "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ, ਅਸੀਂ ਪਰਾਲੀ ਪ੍ਰਬੰਧਨ ਵਿੱਚ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦੇ ਹਾਂ? (How can we assist with stubble management?)"
        elif language == Language.HINDI:
            reply = "नमस्ते जी, हम पराली प्रबंधन में आपकी क्या सहायता कर सकते हैं? (How can we assist with stubble management?)"
        else:
            reply = "Hello, welcome to StubbleOS. How may we assist you with stubble management today?"

    # 8. Optional LLM conversational enhancement
    if llm is not None and not requires_human_escalation:
        try:
            req = LLMRequest.simple(
                user_text=f"Respond courteously in {language.value} to farmer inquiry: {text}",
                purpose="farmer_voice_response",
                max_tokens=128,
            )
            res = await llm.generate(req)
            if res.text.strip():
                reply = res.text.strip()
        except Exception as exc:
            log.debug("farmer_voice_llm_fallback", error=str(exc))

    return FarmerVoiceOutput(
        reply_text=reply,
        language=language,
        detected_intent=intent,
        confidence=confidence,
        requires_human_escalation=requires_human_escalation,
        escalation_reason=escalation_reason,
        action_requested=action_requested,
        booking_draft=booking_draft,
        slots=slots,
    )
