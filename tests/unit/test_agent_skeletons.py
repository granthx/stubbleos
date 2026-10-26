"""Unit tests for skeleton agents (Field Monitor, Weather Window, Farmer Voice, Pricing, MRV)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from stubbleos.agents.farmer_voice.graph import build_farmer_voice_graph
from stubbleos.agents.farmer_voice.logic import process_voice_interaction
from stubbleos.agents.farmer_voice.schemas import FarmerVoiceInput, FarmerVoiceState
from stubbleos.agents.farmer_voice.tools import create_farmer_voice_tools
from stubbleos.agents.field_monitor.graph import build_field_monitor_graph
from stubbleos.agents.field_monitor.logic import detect_field_states
from stubbleos.agents.field_monitor.schemas import FieldMonitorInput, FieldMonitorState
from stubbleos.agents.field_monitor.tools import create_field_monitor_tools
from stubbleos.agents.mrv.graph import build_mrv_graph
from stubbleos.agents.mrv.logic import compute_mrv_evidence
from stubbleos.agents.mrv.schemas import MrvInput, MrvState
from stubbleos.agents.mrv.tools import create_mrv_tools
from stubbleos.agents.pricing_negotiation.graph import build_pricing_negotiation_graph
from stubbleos.agents.pricing_negotiation.logic import calculate_pricing
from stubbleos.agents.pricing_negotiation.schemas import PricingInput, PricingState
from stubbleos.agents.pricing_negotiation.tools import create_pricing_tools
from stubbleos.agents.weather_window.graph import build_weather_window_graph
from stubbleos.agents.weather_window.logic import evaluate_weather_window
from stubbleos.agents.weather_window.schemas import WeatherWindowInput, WeatherWindowState
from stubbleos.agents.weather_window.tools import create_weather_tools
from stubbleos.core.types import FieldState, LandholdingClass, Language, ServiceType
from stubbleos.llm.fake import FakeLLM


# --------------------------------------------------------------------------- Field Monitor
def test_field_monitor() -> None:
    f_id = uuid.uuid4()
    inp = FieldMonitorInput(district="Sangrur", field_ids=[f_id])
    out = detect_field_states(inp)

    assert out.newly_harvested_count == 1
    assert len(out.observations) == 1
    assert out.observations[0].detected_state == FieldState.HARVESTED_RESIDUE_PRESENT

    # Test tools
    tools = create_field_monitor_tools()
    assert len(tools) == 2
    harvest_tool = tools[0]
    res = harvest_tool.invoke({"field_id_str": str(f_id)})
    assert res["harvest_detected"] is True

    # Test graph
    graph = build_field_monitor_graph()
    state = FieldMonitorState(input=inp)
    g_res = graph.invoke(state, config={"configurable": {"thread_id": "fm_t1"}})
    assert g_res["status"] == "completed"

    # Failure mode
    with pytest.raises(ValidationError):
        FieldMonitorInput(district="Sangrur", field_ids=[f_id], extra_bad="1")  # type: ignore[call-arg]


# --------------------------------------------------------------------------- Weather Window
def test_weather_window() -> None:
    inp = WeatherWindowInput(
        district="Sangrur",
        start_date=date(2026, 10, 20),
        end_date=date(2026, 10, 23),
    )
    out = evaluate_weather_window(inp)

    assert len(out.forecasts) == 4
    assert out.workable_days_count == 4
    assert not out.is_rain_predicted

    # Test tools
    tools = create_weather_tools()
    assert len(tools) == 2
    fc_tool = tools[0]
    res = fc_tool.invoke({"district": "Sangrur", "days": 5})
    assert res["district"] == "Sangrur"

    # Test graph
    graph = build_weather_window_graph()
    state = WeatherWindowState(input=inp)
    g_res = graph.invoke(state, config={"configurable": {"thread_id": "ww_t1"}})
    assert g_res["status"] == "completed"

    # Failure mode
    with pytest.raises(ValidationError):
        WeatherWindowInput(district="Sangrur", start_date="invalid_date", end_date="2026-10-23")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- Farmer Voice
@pytest.mark.asyncio
async def test_farmer_voice() -> None:
    f_id = uuid.uuid4()
    fake_llm = FakeLLM(default="ਤੁਹਾਡੀ ਬੇਨਤੀ ਸਵੀਕਾਰ ਕੀਤੀ ਗਈ ਹੈ।")

    inp = FarmerVoiceInput(
        farmer_id=f_id,
        language=Language.PUNJABI,
        inbound_text="ਮੈਨੂੰ ਸੁਪਰ ਸੀਡਰ ਬੁੱਕ ਕਰਨਾ ਹੈ (I want to book super seeder)",
    )
    out = await process_voice_interaction(inp, llm=fake_llm)

    assert out.detected_intent == "book_machine"
    assert out.language == Language.PUNJABI
    assert len(out.reply_text) > 0

    # Test price query without LLM
    inp_price = FarmerVoiceInput(
        farmer_id=f_id,
        inbound_text="What is the price of baling?",
    )
    out_price = await process_voice_interaction(inp_price, llm=None)
    assert out_price.detected_intent == "query_price"
    assert "₹1800" in out_price.reply_text

    # Test general inquiry with failing LLM
    failing_llm = FakeLLM()  # No default response -> raises FakeLLMNoResponse
    inp_general = FarmerVoiceInput(
        farmer_id=f_id,
        inbound_text="Help needed",
    )
    out_general = await process_voice_interaction(inp_general, llm=failing_llm)
    assert out_general.detected_intent == "general_inquiry"

    # Test tools
    tools = create_farmer_voice_tools()
    assert len(tools) == 2
    asr_tool = tools[0]
    res = asr_tool.invoke({"audio_uri": "s3://test.wav", "language": "punjabi"})
    assert "transcript" in res

    # Test graph
    graph = build_farmer_voice_graph(llm=fake_llm)
    state = FarmerVoiceState(input=inp)
    g_res = await graph.ainvoke(state, config={"configurable": {"thread_id": "fv_t1"}})
    assert g_res["status"] == "completed"

    # Failure mode
    with pytest.raises(ValidationError):
        FarmerVoiceInput(farmer_id="not-a-uuid", inbound_text="hello")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- Pricing & Negotiation
def test_pricing_negotiation() -> None:
    f_id = uuid.uuid4()
    field_id = uuid.uuid4()

    # Marginal farmer with concession
    inp_marginal = PricingInput(
        farmer_id=f_id,
        field_id=field_id,
        landholding_class=LandholdingClass.MARGINAL,
        service_type=ServiceType.IN_SITU_SOWING,
        area_acres=2.0,
    )
    out_marginal = calculate_pricing(inp_marginal)
    assert out_marginal.is_concessional is True
    assert out_marginal.quote.subsidy_discount_inr > 0.0
    assert out_marginal.quote.net_price_inr < out_marginal.quote.base_rate_inr

    # Large farmer without concession
    inp_large = PricingInput(
        farmer_id=f_id,
        field_id=field_id,
        landholding_class=LandholdingClass.LARGE,
        service_type=ServiceType.IN_SITU_SOWING,
        area_acres=10.0,
    )
    out_large = calculate_pricing(inp_large)
    assert out_large.is_concessional is False
    assert out_large.quote.subsidy_discount_inr == 0.0

    # Test tools
    tools = create_pricing_tools()
    assert len(tools) == 1
    tariff_tool = tools[0]
    res = tariff_tool.invoke({"area_acres": 2.0, "landholding_class": "marginal"})
    assert res["eligible_for_discount"] is True

    # Test graph
    graph = build_pricing_negotiation_graph()
    state = PricingState(input=inp_marginal)
    g_res = graph.invoke(state, config={"configurable": {"thread_id": "pn_t1"}})
    assert g_res["status"] == "completed"

    # Failure mode: non-positive area
    with pytest.raises(ValidationError):
        PricingInput(
            farmer_id=f_id,
            field_id=field_id,
            landholding_class=LandholdingClass.MARGINAL,
            service_type=ServiceType.IN_SITU_SOWING,
            area_acres=-5.0,
        )


# --------------------------------------------------------------------------- MRV
def test_mrv() -> None:
    field_id = uuid.uuid4()
    inp = MrvInput(field_id=field_id, area_acres=5.0, burn_avoided=True)
    out = compute_mrv_evidence(inp)

    assert out.field_id == field_id
    assert out.impact.burn_avoided is True
    assert out.impact.co2e_kg_avoided > 10000.0  # 5 * 1800 * 1.46 = 13140 kg
    assert len(out.impact.record_sha256) == 64
    assert "not registry-verified" in out.impact.method_note

    # Test tools
    tools = create_mrv_tools()
    assert len(tools) == 1
    tool = tools[0]
    res = tool.invoke({"field_id_str": str(field_id), "area_acres": 5.0})
    assert res["co2e_kg_avoided"] > 0.0

    # Test graph
    graph = build_mrv_graph()
    state = MrvState(input=inp)
    g_res = graph.invoke(state, config={"configurable": {"thread_id": "mrv_t1"}})
    assert g_res["status"] == "completed"

    # Failure mode
    with pytest.raises(ValidationError):
        MrvInput(field_id=field_id, area_acres=-1.0)
