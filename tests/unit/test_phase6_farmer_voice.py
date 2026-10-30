"""Unit tests for Phase 6 Farmer Voice agent."""

from __future__ import annotations

import uuid

import pytest

from stubbleos.agents.farmer_voice.graph import build_farmer_voice_graph
from stubbleos.agents.farmer_voice.logic import (
    classify_intent,
    detect_language,
    process_voice_interaction,
)
from stubbleos.agents.farmer_voice.schemas import (
    FarmerVoiceInput,
    FarmerVoiceState,
)
from stubbleos.agents.farmer_voice.tools import (
    create_extended_farmer_voice_tools,
)
from stubbleos.core.types import Channel, Language, MachineType
from stubbleos.llm.fake import FakeLLM


@pytest.mark.asyncio
async def test_detect_language_and_intent() -> None:
    # Language detection
    assert detect_language("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ") == Language.PUNJABI
    assert detect_language("नमस्ते मुझे मशीन चाहिए") == Language.HINDI
    assert detect_language("Hello I need machine", fallback=Language.ENGLISH) == Language.ENGLISH

    # Intent detection
    intent, conf = classify_intent("ਮੈਂ ਖੇਤ ਨੂੰ ਅੱਗ ਲਾ ਦੇਵਾਂਗਾ ਜੇ ਮਸ਼ੀਨ ਨਾ ਆਈ")
    assert intent == "threat_burn"
    assert conf > 0.95

    intent, _ = classify_intent("ਮੈਨੂੰ ਸੁਪਰ ਸੀਡਰ ਬੁੱਕ ਕਰਨਾ ਹੈ")
    assert intent == "book_machine"

    intent, _ = classify_intent("ਬੇਲਿੰਗ ਦਾ ਰੇਟ ਕਿੰਨਾ ਹੈ?")
    assert intent == "query_price"

    intent, _ = classify_intent("ਮਸ਼ੀਨ ਕਦੋਂ ਆਵੇਗੀ? ਸਥਿਤੀ ਦੱਸੋ")
    assert intent == "check_schedule_status"

    intent, _ = classify_intent("ਹਾਂ ਠੀਕ ਹੈ ਮਨਜ਼ੂਰ")
    assert intent == "confirm_booking"

    intent, _ = classify_intent("ਬੁਕਿੰਗ ਰੱਦ ਕਰ ਦਿਓ")
    assert intent == "cancel_booking"


@pytest.mark.asyncio
async def test_burn_threat_deescalation_and_hitl() -> None:
    f_id = uuid.uuid4()
    inp = FarmerVoiceInput(
        farmer_id=f_id,
        language=Language.PUNJABI,
        inbound_text="ਸਾਡੀ ਕਣਕ ਦੀ ਬਿਜਾਈ ਲੇਟ ਹੋ ਰਹੀ ਹੈ, ਜੇ ਕੱਲ੍ਹ ਮਸ਼ੀਨ ਨਾ ਆਈ ਤਾਂ ਅਸੀਂ ਅੱਗ ਲਗਾ ਦਿਆਂਗੇ!",
    )
    out = await process_voice_interaction(inp)

    assert out.detected_intent == "threat_burn"
    assert out.requires_human_escalation is True
    assert out.escalation_reason == "burn_threat_detected"
    assert out.action_requested == "escalate_to_human"
    assert "ਵੀਰ ਜੀ" in out.reply_text or "ਅੱਗ" in out.reply_text


@pytest.mark.asyncio
async def test_multi_turn_slot_filling() -> None:
    f_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    # Turn 1: Farmer mentions machine but omits acreage
    inp1 = FarmerVoiceInput(
        farmer_id=f_id,
        conversation_id=conv_id,
        language=Language.PUNJABI,
        inbound_text="ਮੈਨੂੰ ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ",
    )
    out1 = await process_voice_interaction(inp1)
    assert out1.detected_intent == "book_machine"
    assert out1.slots is not None
    assert out1.slots.machine_type == MachineType.SUPER_SEEDER
    assert out1.slots.area_acres is None
    assert "ਏਕੜ" in out1.reply_text or "ਕਿੱਲੇ" in out1.reply_text

    # Turn 2: Farmer provides acreage and village
    inp2 = FarmerVoiceInput(
        farmer_id=f_id,
        conversation_id=conv_id,
        language=Language.PUNJABI,
        inbound_text="ਮੇਰੇ ਕੋਲ ਪਿੰਡ Nabha ਵਿੱਚ 4 ਏਕੜ ਜ਼ਮੀਨ ਹੈ",
    )
    out2 = await process_voice_interaction(inp2, current_slots=out1.slots)
    assert out2.slots is not None
    assert out2.slots.area_acres == 4.0
    assert out2.slots.machine_type == MachineType.SUPER_SEEDER
    assert "Nabha" in (out2.slots.village or "")
    # Prompts for confirmation
    assert "ਪੁਸ਼ਟੀ" in out2.reply_text or "confirm" in out2.reply_text.lower() or "4.0" in out2.reply_text

    # Turn 3: Farmer confirms booking
    inp3 = FarmerVoiceInput(
        farmer_id=f_id,
        conversation_id=conv_id,
        language=Language.PUNJABI,
        inbound_text="ਹਾਂ, ਬੁਕਿੰਗ ਪੱਕੀ ਕਰੋ (Yes confirm)",
    )
    out3 = await process_voice_interaction(inp3, current_slots=out2.slots)
    assert out3.booking_draft is not None
    assert out3.booking_draft.area_acres == 4.0
    assert out3.booking_draft.machine_type == MachineType.SUPER_SEEDER
    assert out3.action_requested == "submit_booking"


@pytest.mark.asyncio
async def test_hindi_conversational_flow() -> None:
    f_id = uuid.uuid4()
    inp = FarmerVoiceInput(
        farmer_id=f_id,
        language=Language.HINDI,
        inbound_text="मुझे गाँव Sangrur में 5 एकड़ के लिए सुपर सीडर चाहिए",
    )
    out = await process_voice_interaction(inp)
    assert out.language == Language.HINDI
    assert out.slots is not None
    assert out.slots.area_acres == 5.0
    assert out.slots.machine_type == MachineType.SUPER_SEEDER
    assert "पुष्टि" in out.reply_text or "5.0" in out.reply_text


@pytest.mark.asyncio
async def test_farmer_voice_graph_execution() -> None:
    fake_llm = FakeLLM(default="ਤੁਹਾਡੀ ਬੇਨਤੀ ਦਰਜ ਕਰ ਲਈ ਗਈ ਹੈ।")
    graph = build_farmer_voice_graph(llm=fake_llm)

    f_id = uuid.uuid4()
    inp = FarmerVoiceInput(
        farmer_id=f_id,
        language=Language.PUNJABI,
        channel=Channel.VOICE,
        inbound_text="ਮੈਨੂੰ ਬੇਲਰ ਚਾਹੀਦਾ ਹੈ",
    )
    state = FarmerVoiceState(input=inp)
    res = await graph.ainvoke(state, config={"configurable": {"thread_id": "fv_t6"}})

    assert res["status"] == "completed"
    assert len(res["turns"]) >= 2
    assert res["output"].audio_uri is not None
    assert res["output"].audio_uri.startswith("s3://")


def test_extended_tools_and_memory() -> None:
    tools = create_extended_farmer_voice_tools()
    assert len(tools) == 4

    # Profile lookup
    prof_tool = next(t for t in tools if t.name == "lookup_farmer_profile_tool")
    p_res = prof_tool.invoke({"farmer_id": str(uuid.uuid4())})
    assert p_res["landholding_class"] == "marginal"
    assert p_res["eligible_for_subsidy"] is True

    # Policy search
    mem_tool = next(t for t in tools if t.name == "search_policy_memory_tool")
    m_res = mem_tool.invoke({"query": "subsidy on super seeder"})
    assert len(m_res["results"]) > 0
    assert any("subsidy" in r["text"].lower() for r in m_res["results"])
