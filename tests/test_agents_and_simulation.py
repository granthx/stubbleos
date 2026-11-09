"""Consolidated agents and simulation test suite for StubbleOS."""

from __future__ import annotations

# ==============================================================================
# Section: test_farmer_voice.py
# ==============================================================================
"""Unit tests for Farmer Voice agent."""


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


# ==============================================================================
# Section: test_dialogue_failure_modes.py
# ==============================================================================
"""Unit tests for edge cases and failure modes."""


from datetime import datetime

import pytest
from pydantic import ValidationError

from stubbleos.agents.pricing_negotiation.schemas import BiomassOffer, PricingInput
from stubbleos.channels.models import OutboundMessage
from stubbleos.channels.router import ChannelRouter
from stubbleos.channels.whatsapp import WhatsAppChannel
from stubbleos.core.clock import IST, SimClock
from stubbleos.core.events import InMemoryEventBus
from stubbleos.core.types import LandholdingClass, ServiceType


@pytest.mark.asyncio
async def test_invalid_phone_number_delivery_failure() -> None:
    wa = WhatsAppChannel()

    # Invalid phone number (letters, too short)
    msg = OutboundMessage(
        recipient_id="invalid-phone-123",
        channel=Channel.WHATSAPP,
        text="Hello",
    )
    res = await wa.send_message(msg)
    assert res.success is False
    assert res.status == "failed"
    assert "Invalid WhatsApp phone number" in (res.error or "")


@pytest.mark.asyncio
async def test_empty_or_whitespace_voice_input() -> None:
    f_id = uuid.uuid4()
    inp = FarmerVoiceInput(
        farmer_id=f_id,
        inbound_text="    ",
    )
    out = await process_voice_interaction(inp)
    assert out.detected_intent == "general_inquiry"
    assert len(out.reply_text) > 0


def test_pricing_validation_errors() -> None:
    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()

    # Zero or negative area acres
    with pytest.raises(ValidationError):
        PricingInput(
            farmer_id=f_id,
            field_id=fld_id,
            landholding_class=LandholdingClass.SMALL,
            service_type=ServiceType.IN_SITU_SOWING,
            area_acres=0.0,
        )

    # Negative price per tonne
    with pytest.raises(ValidationError):
        BiomassOffer(
            buyer_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            proposed_price_per_tonne_inr=-500.0,
            tonnes=100.0,
        )


@pytest.mark.asyncio
async def test_channel_router_unregistered_channel() -> None:
    router = ChannelRouter(channels={})

    # Asking for an unregistered channel without fallback raises ValueError
    with pytest.raises(ValueError, match="No adapter registered"):
        router.get_channel(Channel.WHATSAPP)


@pytest.mark.asyncio
async def test_channel_pii_redaction_in_event_bus() -> None:
    clock = SimClock(start=datetime(2026, 10, 30, 14, 0, tzinfo=IST))
    event_bus = InMemoryEventBus(clock=clock)
    received_events: list[str] = []

    async def audit_listener(event) -> None:
        received_events.append(event.payload.get("message_text", ""))

    event_bus.subscribe("farmer.inbound_message", audit_listener)

    router = ChannelRouter(
        event_bus=event_bus,
        clock=clock,
        enforce_quiet_hours=False,
    )

    # Inbound message containing sensitive phone number and Aadhaar number
    payload = {
        "sender_id": "+919876543210",
        "text": "Call me at +919876543210 and my Aadhaar is 2345 6789 0123",
    }

    f_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    await router.handle_inbound(
        channel_type=Channel.MOCK,
        payload=payload,
        farmer_id=f_id,
        conversation_id=conv_id,
    )

    assert len(received_events) == 1
    event_text = received_events[0]

    # Verify that the event bus received REDACTED content
    assert "+919876543210" not in event_text
    assert "2345 6789 0123" not in event_text
    assert "[REDACTED]" in event_text


# ==============================================================================
# Section: test_field_monitor.py
# ==============================================================================
from stubbleos.data.models import Approval, AuditLog, Consent, ImpactRecord, MrvEvidence, Plan

"""Unit and simulation accuracy tests for Field Monitor agent."""


import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from stubbleos.agents.field_monitor.graph import build_field_monitor_graph
from stubbleos.agents.field_monitor.logic import (
    build_field_events,
    evaluate_field_observation,
)
from stubbleos.agents.field_monitor.schemas import (
    FieldMonitorInput,
    FieldMonitorState,
    FieldObservationRequest,
)
from stubbleos.core.config import Settings
from stubbleos.core.types import FieldState
from stubbleos.data.models import Base
from stubbleos.data.repositories import ApprovalRepository
from stubbleos.simulation.sensor import DistrictSensorModel, SensorConfig

TABLES = [
    Consent.__table__,
    MrvEvidence.__table__,
    ImpactRecord.__table__,
    AuditLog.__table__,
    Approval.__table__,
    Plan.__table__,
]


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"core": None, "pii": None})
    Base.metadata.create_all(engine, tables=TABLES)
    sm = sessionmaker(engine, expire_on_commit=False)
    with sm() as s:
        yield s
    engine.dispose()


@pytest.fixture
def approval_repo(session: Session) -> ApprovalRepository:
    return ApprovalRepository(session)


def test_field_monitor_all_four_states() -> None:
    """Verifies that Field Monitor correctly classifies all four domain states."""
    f_id = uuid.uuid4()

    # 1. NOT_HARVESTED: high NDVI, negative BSI, no fires
    req_not_harvested = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.72,
        current_ndvi=0.70,
        current_bsi=-0.25,
        has_firms_hotspot=False,
    )
    res_not_harvested = evaluate_field_observation(req_not_harvested)
    assert res_not_harvested.detected_state == FieldState.NOT_HARVESTED
    assert res_not_harvested.confidence >= 0.75
    assert res_not_harvested.requires_approval is False

    # 2. HARVESTED_RESIDUE_PRESENT: significant drop in NDVI (>0.25), low BSI
    req_harvested = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.72,
        current_ndvi=0.30,  # drop = 0.42
        current_bsi=-0.05,
        has_firms_hotspot=False,
    )
    res_harvested = evaluate_field_observation(req_harvested)
    assert res_harvested.detected_state == FieldState.HARVESTED_RESIDUE_PRESENT
    assert res_harvested.confidence >= 0.80

    # 3. CLEARED: high Bare Soil Index (BSI >= 0.15)
    req_cleared = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.72,
        current_ndvi=0.22,
        current_bsi=0.28,  # > 0.15 bare soil
        has_firms_hotspot=False,
    )
    res_cleared = evaluate_field_observation(req_cleared)
    assert res_cleared.detected_state == FieldState.CLEARED
    assert res_cleared.confidence >= 0.80

    # 4. BURN_DETECTED: active FIRMS thermal hotspot
    req_burn = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.72,
        current_ndvi=0.15,
        current_bsi=0.20,
        has_firms_hotspot=True,
        firms_confidence_pct=92.0,
    )
    res_burn = evaluate_field_observation(req_burn)
    assert res_burn.detected_state == FieldState.BURN_DETECTED
    assert res_burn.confidence >= 0.90
    assert res_burn.has_thermal_anomaly is True


def test_field_monitor_low_confidence_routes_to_approval(approval_repo: ApprovalRepository) -> None:
    """Verifies that an observation with confidence below threshold escalates to the approval queue."""
    custom_settings = Settings(
        field_monitor_min_confidence_approval=0.85,  # Strict threshold
        ndvi_harvest_drop_threshold=0.25,
    )

    f_id = uuid.uuid4()
    # Marginal observation: NDVI drop is just on the boundary (drop 0.26)
    req = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.60,
        current_ndvi=0.34,  # drop = 0.26
        current_bsi=-0.15,
        has_firms_hotspot=False,
    )
    res = evaluate_field_observation(req, settings=custom_settings)

    # Should flag approval required
    assert res.requires_approval is True
    assert "low confidence" in (res.approval_reason or "").lower()

    # Test LangGraph escalation node creates Approval record
    inp = FieldMonitorInput(district="Sangrur", fields=[req])
    state = FieldMonitorState(input=inp)
    graph = build_field_monitor_graph(approval_repo=approval_repo, settings=custom_settings)
    result_state = graph.invoke(state, config={"configurable": {"thread_id": "fm_low_conf"}})

    assert result_state["status"] == "completed"
    assert len(result_state["created_approval_ids"]) == 1

    appr = approval_repo.get_by_id(result_state["created_approval_ids"][0])
    assert appr is not None
    assert appr.kind == "field_state_change"
    assert appr.subject_id == f_id


@pytest.mark.asyncio
async def test_field_monitor_event_emission() -> None:
    """Verifies that FieldStateChanged and BurnDetected events are emitted."""
    f_id = uuid.uuid4()

    # Burn detection emits both BurnDetected and FieldStateChanged
    req_burn = FieldObservationRequest(
        field_id=f_id,
        previous_state=FieldState.HARVESTED_RESIDUE_PRESENT,
        has_firms_hotspot=True,
        firms_confidence_pct=88.0,
    )
    res_burn = evaluate_field_observation(req_burn)
    events = build_field_events(res_burn)

    types = {e.event_type for e in events}
    assert "field.burn_detected" in types
    assert "field.state_changed" in types

    # Unchanged state emits no events
    req_same = FieldObservationRequest(
        field_id=f_id,
        previous_state=FieldState.NOT_HARVESTED,
        pre_harvest_ndvi=0.75,
        current_ndvi=0.73,
    )
    res_same = evaluate_field_observation(req_same)
    events_same = build_field_events(res_same)
    assert len(events_same) == 0


def test_field_monitor_accuracy_on_synthetic_ground_truth() -> None:
    """Simulates 100 fields with controllable sensor noise and verifies high detection accuracy."""
    rng = np.random.default_rng(2026)
    sensor_model = DistrictSensorModel(
        SensorConfig(
            cloud_cover_prob=0.05,
            thermal_false_positive_prob=0.01,
            thermal_false_negative_prob=0.03,
            ndvi_noise_std=0.02,
            bsi_noise_std=0.02,
        )
    )

    states_pool = [
        FieldState.NOT_HARVESTED,
        FieldState.HARVESTED_RESIDUE_PRESENT,
        FieldState.CLEARED,
        FieldState.BURN_DETECTED,
    ]

    ground_truth: list[FieldState] = []
    detected: list[FieldState] = []

    for _ in range(100):
        f_id = uuid.uuid4()
        true_state = rng.choice(states_pool)
        ground_truth.append(true_state)

        # Generate noisy synthetic observation
        obs = sensor_model.generate_observation(f_id, true_state, rng)

        # If not cloud-obscured, classify
        if not obs.is_cloud_obscured:
            req = sensor_model.to_observation_request(obs, previous_state=FieldState.NOT_HARVESTED)
            res = evaluate_field_observation(req)
            detected.append(res.detected_state)
        else:
            # Fallback to previous state on heavy cloud cover
            detected.append(FieldState.NOT_HARVESTED)

    metrics = DistrictSensorModel.calculate_accuracy_metrics(ground_truth, detected)

    # Verify sensor precision and recall vs simulated ground truth
    assert metrics["overall_accuracy"] >= 0.85
    assert metrics["burn_precision"] >= 0.85
    assert metrics["burn_recall"] >= 0.85
    assert metrics["burn_f1"] >= 0.85


# ==============================================================================
# Section: test_weather_window.py
# ==============================================================================
"""Unit tests for Weather & Window agent."""


from datetime import date, timedelta

from stubbleos.agents.weather_window.graph import build_weather_window_graph
from stubbleos.agents.weather_window.logic import (
    build_replan_event,
    evaluate_weather_window,
    find_contiguous_workable_blocks,
)
from stubbleos.agents.weather_window.schemas import (
    DailyForecast,
    WeatherWindowInput,
    WeatherWindowState,
)
from stubbleos.core.types import ReplanReason


def test_contiguous_workable_blocks() -> None:
    """Verifies that contiguous workable sequences are correctly identified."""
    d0 = date(2026, 10, 20)
    forecasts = [
        DailyForecast(forecast_date=d0, is_workable=True),
        DailyForecast(forecast_date=d0 + timedelta(days=1), is_workable=True),
        DailyForecast(forecast_date=d0 + timedelta(days=2), is_workable=False),  # Rain
        DailyForecast(forecast_date=d0 + timedelta(days=3), is_workable=True),
        DailyForecast(forecast_date=d0 + timedelta(days=4), is_workable=True),
        DailyForecast(forecast_date=d0 + timedelta(days=5), is_workable=False),  # High wind
    ]

    blocks = find_contiguous_workable_blocks(forecasts)
    assert len(blocks) == 2
    assert blocks[0] == (d0, d0 + timedelta(days=1))
    assert blocks[1] == (d0 + timedelta(days=3), d0 + timedelta(days=4))


def test_weather_window_safe_operations_and_deadlines() -> None:
    """Verifies per-field deadline tracking and urgency classification."""
    current_dt = date(2026, 10, 20)
    f1 = uuid.uuid4()
    f2 = uuid.uuid4()

    # Field 1 has 3 days to deadline; Field 2 has 12 days to deadline
    deadlines = {
        f1: current_dt + timedelta(days=3),
        f2: current_dt + timedelta(days=12),
    }

    forecasts = [
        DailyForecast(forecast_date=current_dt, is_workable=True),
        DailyForecast(forecast_date=current_dt + timedelta(days=1), precipitation_mm=10.0, is_workable=False),
        DailyForecast(forecast_date=current_dt + timedelta(days=2), precipitation_mm=8.0, is_workable=False),
        DailyForecast(forecast_date=current_dt + timedelta(days=3), is_workable=True),
    ]

    inp = WeatherWindowInput(
        district="Sangrur",
        current_date=current_dt,
        field_deadlines=deadlines,
        forecasts=forecasts,
    )
    out = evaluate_weather_window(inp)

    f1_win = next(w for w in out.field_windows if w.field_id == f1)
    f2_win = next(w for w in out.field_windows if w.field_id == f2)

    assert f1_win.days_remaining_to_deadline == 3
    # Field 1 has 3 days remaining and only 2 workable days -> high urgency
    assert f1_win.urgency_level in {"high", "critical"}

    assert f2_win.days_remaining_to_deadline == 12
    assert f2_win.urgency_level == "low"


def test_weather_window_replan_triggered_on_rain_shock() -> None:
    """Verifies that a forecast shift in precipitation triggers a ReplanTriggered event."""
    d0 = date(2026, 10, 20)
    d1 = date(2026, 10, 21)

    prev_forecasts = [
        DailyForecast(forecast_date=d0, precipitation_mm=0.0),
        DailyForecast(forecast_date=d1, precipitation_mm=0.0),
    ]

    # Shift: 15mm sudden unpredicted rain on d1 (delta 15.0mm >= threshold 5.0mm)
    new_forecasts = [
        DailyForecast(forecast_date=d0, precipitation_mm=0.0),
        DailyForecast(forecast_date=d1, precipitation_mm=15.0, is_workable=False),
    ]

    inp = WeatherWindowInput(
        district="Sangrur",
        current_date=d0,
        forecasts=new_forecasts,
        previous_forecasts=prev_forecasts,
    )

    out = evaluate_weather_window(inp)
    assert out.is_replan_triggered is True
    assert out.replan_reason == "rain_forecast_change"
    assert "15.0" in out.replan_details["max_rain_delta_mm"]

    event = build_replan_event(out)
    assert event is not None
    assert event.reason == ReplanReason.RAIN_FORECAST_CHANGE
    assert event.district == "Sangrur"


def test_weather_window_graph_execution() -> None:
    """Verifies LangGraph state execution with event emission."""
    d0 = date(2026, 10, 20)
    event_bus = InMemoryEventBus()

    inp = WeatherWindowInput(
        district="Sangrur",
        current_date=d0,
        forecasts=[
            DailyForecast(forecast_date=d0, precipitation_mm=20.0, is_workable=False),
        ],
        previous_forecasts=[
            DailyForecast(forecast_date=d0, precipitation_mm=0.0),
        ],
    )

    state = WeatherWindowState(input=inp)
    graph = build_weather_window_graph(event_bus=event_bus)
    result_state = graph.invoke(state, config={"configurable": {"thread_id": "ww_test"}})

    assert result_state["status"] == "completed"
    assert result_state["replan_event_emitted"] is True
    assert len(event_bus.history) == 1
    assert event_bus.history[0].event_type == "plan.replan_triggered"


# ==============================================================================
# Section: test_agent_machine_scheduler.py
# ==============================================================================
"""Unit and invariant tests for Machine Scheduler agent."""


import pytest

from stubbleos.agents.machine_scheduler.graph import build_machine_scheduler_graph
from stubbleos.agents.machine_scheduler.logic import run_machine_scheduler
from stubbleos.agents.machine_scheduler.schemas import (
    MachineSchedulerInput,
    MachineSchedulerState,
)
from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
    SchedulerConfig,
)


@pytest.fixture
def sample_jobs_and_machines() -> tuple[list[JobRequest], list[MachineResource]]:
    jobs = [
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=48.0,
            center_lat=30.25,
            center_lon=75.80,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.MARGINAL,
            area_acres=2.5,
            earliest_start_hour=0.0,
            deadline_hour=36.0,
            center_lat=30.26,
            center_lon=75.82,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
    ]
    machines = [
        MachineResource(
            machine_id=uuid.uuid4(),
            machine_type=MachineType.HAPPY_SEEDER,
            capacity_acres_per_hour=1.5,
            hourly_cost_inr=800.0,
            current_lat=30.24,
            current_lon=75.79,
            available_from_hour=0.0,
        )
    ]
    return jobs, machines


@pytest.mark.asyncio
async def test_machine_scheduler_cpsat(
    sample_jobs_and_machines: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    jobs, machines = sample_jobs_and_machines
    fake_llm = FakeLLM(default="CP-SAT prioritised marginal smallholder with tight deadline.")

    input_data = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="cpsat",
        config=SchedulerConfig(time_limit_seconds=0.2),
        request_explanation=True,
    )

    output = await run_machine_scheduler(input_data, llm=fake_llm)

    assert len(output.assignments) > 0
    assert output.solver_status in {"OPTIMAL", "FEASIBLE"}
    assert "CP-SAT prioritised" in output.explanation
    assert output.mode_used == "cpsat"


@pytest.mark.asyncio
async def test_machine_scheduler_auction(
    sample_jobs_and_machines: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    jobs, machines = sample_jobs_and_machines
    fake_llm = FakeLLM(default="Contract-Net auction awarded task to closest idle machine.")

    input_data = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="auction",
        current_hour=0.0,
        request_explanation=True,
    )

    output = await run_machine_scheduler(input_data, llm=fake_llm)

    assert len(output.assignments) > 0
    assert output.mode_used == "auction"
    assert "Contract-Net auction" in output.explanation
    assert len(output.audit_logs) > 0


@pytest.mark.asyncio
async def test_llm_invariant_does_not_alter_assignments(
    sample_jobs_and_machines: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    """CRITICAL TEST: Ensure LLM outputs cannot mutate the optimizer assignment list."""
    jobs, machines = sample_jobs_and_machines

    # Malicious fake LLM attempting to claim different assignments or inject hallucinated fields
    fake_llm = FakeLLM(default='{"hallucinated_assignment": "reassign_all_fields_to_bogus_machine"}')

    input_data = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="cpsat",
        request_explanation=True,
    )

    output = await run_machine_scheduler(input_data, llm=fake_llm)

    # Validates that all assignments belong only to valid input fields and machines
    valid_field_ids = {j.field_id for j in jobs}
    valid_machine_ids = {m.machine_id for m in machines}

    for a in output.assignments:
        assert a.field_id in valid_field_ids
        assert a.machine_id in valid_machine_ids


@pytest.mark.asyncio
async def test_machine_scheduler_graph(
    sample_jobs_and_machines: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    jobs, machines = sample_jobs_and_machines
    fake_llm = FakeLLM(default="Graph allocation completed.")

    graph = build_machine_scheduler_graph(llm=fake_llm)

    input_data = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="cpsat",
        request_explanation=True,
    )
    state = MachineSchedulerState(input=input_data)
    res = await graph.ainvoke(state, config={"configurable": {"thread_id": "ms_test"}})

    assert res["status"] == "completed"
    assert len(res["assignments"]) > 0


def test_machine_scheduler_failure_mode_bad_data() -> None:
    """Failure-mode test: Malformed input data is rejected by Pydantic."""
    with pytest.raises(ValidationError):
        MachineSchedulerInput(
            jobs=[],
            machines=[],
            mode="unsupported_quantum_mode",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_machine_scheduler_failure_mode_infeasible_empty() -> None:
    """Failure-mode test: Empty machinery fleet returns zero assignments safely."""
    job = JobRequest(
        field_id=uuid.uuid4(),
        farmer_id=uuid.uuid4(),
        landholding_class=LandholdingClass.SMALL,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=24.0,
        center_lat=30.0,
        center_lon=75.0,
        eligible_machine_types=[MachineType.HAPPY_SEEDER],
    )
    input_data = MachineSchedulerInput(
        jobs=[job],
        machines=[],  # No machines available!
        mode="cpsat",
        request_explanation=False,
    )

    output = await run_machine_scheduler(input_data)
    assert len(output.assignments) == 0
    assert job.field_id in output.unassigned_job_ids


# ==============================================================================
# Section: test_agent_logistics.py
# ==============================================================================
"""Unit tests for Logistics agent."""


import pytest

from stubbleos.agents.logistics.graph import build_logistics_graph
from stubbleos.agents.logistics.logic import run_logistics
from stubbleos.agents.logistics.schemas import LogisticsInput, LogisticsState
from stubbleos.agents.logistics.tools import create_logistics_tools
from stubbleos.optimization.routing import (
    BuyerDropoff,
    FieldPickup,
    RoutingConfig,
    TruckSpec,
)


@pytest.fixture
def sample_logistics_entities() -> tuple[list[FieldPickup], list[BuyerDropoff], list[TruckSpec]]:
    pickups = [
        FieldPickup(
            field_id=uuid.uuid4(),
            lat=30.25,
            lon=75.80,
            tonnes=12.0,
            moisture_pct=14.0,
            ready_hour=0.0,
            deadline_hour=72.0,
        ),
        FieldPickup(
            field_id=uuid.uuid4(),
            lat=30.28,
            lon=75.83,
            tonnes=8.0,
            moisture_pct=13.5,
            ready_hour=0.0,
            deadline_hour=72.0,
        ),
    ]
    dropoffs = [
        BuyerDropoff(
            buyer_id=uuid.uuid4(),
            lat=30.35,
            lon=75.90,
            max_moisture_pct=16.0,
            capacity_tonnes=50.0,
            open_hour=0.0,
            close_hour=840.0,
        )
    ]
    trucks = [
        TruckSpec(
            truck_id=uuid.uuid4(),
            capacity_tonnes=15.0,
            cost_per_km_inr=45.0,
            co2_kg_per_km=1.42,
            depot_lat=30.20,
            depot_lon=75.75,
            speed_kmh=40.0,
        )
    ]
    return pickups, dropoffs, trucks


@pytest.mark.asyncio
async def test_run_logistics(
    sample_logistics_entities: tuple[list[FieldPickup], list[BuyerDropoff], list[TruckSpec]],
) -> None:
    pickups, dropoffs, trucks = sample_logistics_entities
    fake_llm = FakeLLM(default="Biomass freight routes dispatched efficiently.")

    input_data = LogisticsInput(
        pickups=pickups,
        dropoffs=dropoffs,
        trucks=trucks,
        config=RoutingConfig(time_limit_seconds=0.2),
        request_explanation=True,
    )

    output = await run_logistics(input_data, llm=fake_llm)

    assert "ROUTED" in output.solver_status
    assert output.total_delivered_tonnes > 0
    assert output.total_distance_km > 0
    assert output.total_cost_inr > 0
    assert output.total_co2_kg > 0
    assert "Biomass freight routes" in output.explanation

    # Test without LLM -> fallback summary
    output_no_llm = await run_logistics(input_data, llm=None)
    assert "Generated" in output_no_llm.explanation

    # Test with failing LLM -> fallback summary
    failing_llm = FakeLLM()
    output_failing_llm = await run_logistics(input_data, llm=failing_llm)
    assert "Generated" in output_failing_llm.explanation


@pytest.mark.asyncio
async def test_logistics_graph(
    sample_logistics_entities: tuple[list[FieldPickup], list[BuyerDropoff], list[TruckSpec]],
) -> None:
    pickups, dropoffs, trucks = sample_logistics_entities
    fake_llm = FakeLLM(default="Logistics workflow solved.")
    graph = build_logistics_graph(llm=fake_llm)

    input_data = LogisticsInput(
        pickups=pickups,
        dropoffs=dropoffs,
        trucks=trucks,
        config=RoutingConfig(time_limit_seconds=0.2),
        request_explanation=True,
    )
    state = LogisticsState(input=input_data)
    res = await graph.ainvoke(state, config={"configurable": {"thread_id": "log_test"}})

    assert res["status"] == "completed"
    assert len(res["routes"]) > 0


def test_logistics_tools() -> None:
    tools = create_logistics_tools()
    assert len(tools) == 1
    tool = tools[0]
    res = tool.invoke({"pickup_count": 2, "dropoff_count": 1, "truck_count": 1})
    assert res["status"] == "ready"


def test_logistics_failure_mode_bad_data() -> None:
    """Failure-mode test: Malformed input data is rejected by Pydantic."""
    with pytest.raises(ValidationError):
        LogisticsInput(
            pickups=[],
            dropoffs=[],
            trucks=[],
            illegal_attr=123,  # type: ignore[call-arg]
        )


# ==============================================================================
# Section: test_agent_buyer_demand.py
# ==============================================================================
"""Unit tests for Buyer Demand agent."""


import pytest

from stubbleos.agents.buyer_demand.graph import build_buyer_demand_graph
from stubbleos.agents.buyer_demand.logic import build_order_book
from stubbleos.agents.buyer_demand.schemas import (
    BuyerDemandInput,
    BuyerDemandState,
    BuyerOrderModel,
)
from stubbleos.agents.buyer_demand.tools import create_buyer_demand_tools
from stubbleos.core.types import BuyerType, OrderStatus


@pytest.fixture
def sample_orders() -> list[BuyerOrderModel]:
    return [
        BuyerOrderModel(
            order_id=uuid.uuid4(),
            buyer_id=uuid.uuid4(),
            buyer_name="Punjab Biomass Power Plant",
            buyer_type=BuyerType.BIOMASS_PLANT,
            district="Sangrur",
            tonnes_required=100.0,
            tonnes_filled=20.0,
            price_inr_per_tonne=2000.0,
            max_moisture_pct=15.0,
            window_start=date(2026, 10, 15),
            window_end=date(2026, 11, 15),
            status=OrderStatus.OPEN,
        ),
        BuyerOrderModel(
            order_id=uuid.uuid4(),
            buyer_id=uuid.uuid4(),
            buyer_name="Ludhiana Bio-CNG Refinery",
            buyer_type=BuyerType.CBG_PLANT,
            district="Sangrur",
            tonnes_required=50.0,
            tonnes_filled=0.0,
            price_inr_per_tonne=2200.0,
            max_moisture_pct=12.0,
            window_start=date(2026, 10, 20),
            window_end=date(2026, 11, 20),
            status=OrderStatus.OPEN,
        ),
    ]


@pytest.mark.asyncio
async def test_build_order_book(sample_orders: list[BuyerOrderModel]) -> None:
    fake_llm = FakeLLM(default="Commercial demand outlook is strong in Sangrur.")

    input_data = BuyerDemandInput(
        district="Sangrur",
        target_date=date(2026, 10, 25),
        orders=sample_orders,
        request_explanation=True,
    )

    book = await build_order_book(input_data, llm=fake_llm)

    assert book.district == "Sangrur"
    assert book.total_tonnes_demanded == 150.0
    assert book.total_tonnes_filled == 20.0
    assert book.open_tonnes == 130.0
    assert book.min_price_inr_per_tonne == 2000.0
    assert book.max_price_inr_per_tonne == 2200.0
    # Weighted avg: (80*2000 + 50*2200) / 130 = (160000 + 110000) / 130 = 270000 / 130 = ~2076.92
    assert 2075.0 <= book.weighted_avg_price_inr_per_tonne <= 2080.0
    assert "Commercial demand outlook" in book.explanation


@pytest.mark.asyncio
async def test_order_book_moisture_filter(sample_orders: list[BuyerOrderModel]) -> None:
    # Filter for buyers that accept residue with at least 14% moisture
    input_data = BuyerDemandInput(
        district="Sangrur",
        orders=sample_orders,
        max_moisture_pct_filter=14.0,
        request_explanation=False,
    )

    book = await build_order_book(input_data)
    # The 12% moisture limit order should be filtered out
    assert len(book.orders) == 1
    assert book.orders[0].buyer_name == "Punjab Biomass Power Plant"


@pytest.mark.asyncio
async def test_buyer_demand_graph(sample_orders: list[BuyerOrderModel]) -> None:
    fake_llm = FakeLLM(default="Graph order book published.")
    graph = build_buyer_demand_graph(llm=fake_llm)

    input_data = BuyerDemandInput(
        district="Sangrur",
        orders=sample_orders,
        request_explanation=True,
    )
    state = BuyerDemandState(input=input_data)
    res = await graph.ainvoke(state, config={"configurable": {"thread_id": "bd_test"}})

    assert res["status"] == "published"
    assert res["order_book"] is not None
    assert res["order_book"].open_tonnes == 130.0


def test_buyer_demand_tools() -> None:
    tools = create_buyer_demand_tools()
    assert len(tools) == 1
    tool = tools[0]
    res = tool.invoke({"district": "Sangrur"})
    assert res["district"] == "Sangrur"
    assert res["status"] == "ready"


def test_buyer_demand_failure_mode_bad_data() -> None:
    """Failure-mode test: Malformed request is rejected by schema."""
    with pytest.raises(ValidationError):
        BuyerDemandInput(
            district="Sangrur",
            illegal_key="invalid",  # type: ignore[call-arg]
        )


@pytest.mark.asyncio
async def test_buyer_demand_failure_mode_empty_orders() -> None:
    """Failure-mode test: Empty order book returns zero metrics safely."""
    input_data = BuyerDemandInput(
        district="EmptyDistrict",
        orders=[],
        request_explanation=False,
    )
    book = await build_order_book(input_data)
    assert book.total_tonnes_demanded == 0.0
    assert book.open_tonnes == 0.0
    assert book.min_price_inr_per_tonne == 0.0
    assert len(book.orders) == 0


# ==============================================================================
# Section: test_pricing_negotiation.py
# ==============================================================================
"""Unit tests for Pricing & Negotiation agent."""


from stubbleos.agents.pricing_negotiation.graph import build_pricing_negotiation_graph
from stubbleos.agents.pricing_negotiation.logic import (
    calculate_pricing,
    draft_contract_terms,
    negotiate_biomass_bid,
)
from stubbleos.agents.pricing_negotiation.schemas import (
    PricingState,
)


def test_concessional_pricing_and_surge_protection() -> None:
    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()

    # 1. Marginal farmer (<2.5 acres): gets 25% FPO subsidy discount, protected from surge
    inp_marginal = PricingInput(
        farmer_id=f_id,
        field_id=fld_id,
        landholding_class=LandholdingClass.MARGINAL,
        service_type=ServiceType.IN_SITU_SOWING,
        area_acres=2.0,
        days_to_deadline=2,  # Urgent deadline
        machine_scarcity_ratio=2.0,  # High scarcity
    )
    out_marginal = calculate_pricing(inp_marginal)
    assert out_marginal.is_concessional is True
    assert out_marginal.quote.base_rate_inr == 2400.0  # 2 acres * 1200
    assert out_marginal.quote.subsidy_discount_inr == 600.0  # 25% of 2400
    assert out_marginal.quote.surge_amount_inr == 0.0  # Protected from surge!
    assert out_marginal.quote.net_price_inr == 1800.0

    # Settlement breakdown check
    assert out_marginal.quote.operator_receivable_inr == 1350.0  # 75%
    assert out_marginal.quote.logistics_share_inr == 270.0  # 15%
    assert out_marginal.quote.platform_fee_inr == 180.0  # 10%

    # 2. Large farmer: standard rate + surge applied
    inp_large = PricingInput(
        farmer_id=f_id,
        field_id=fld_id,
        landholding_class=LandholdingClass.LARGE,
        service_type=ServiceType.IN_SITU_SOWING,
        area_acres=10.0,
        days_to_deadline=2,  # Urgent deadline -> +15%
        machine_scarcity_ratio=2.0,  # High scarcity -> +10%
    )
    out_large = calculate_pricing(inp_large)
    assert out_large.is_concessional is False
    assert out_large.quote.base_rate_inr == 12000.0
    assert out_large.quote.subsidy_discount_inr == 0.0
    assert out_large.quote.surge_amount_inr == 3000.0  # 25% surge total
    assert out_large.quote.net_price_inr == 15000.0


def test_moisture_penalty_deduction() -> None:
    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()

    # Straw with 18% moisture (excess = 4% over 14% threshold)
    inp_wet = PricingInput(
        farmer_id=f_id,
        field_id=fld_id,
        landholding_class=LandholdingClass.MEDIUM,
        service_type=ServiceType.BALING,
        area_acres=5.0,
        estimated_tonnes=10.0,
        moisture_pct=18.0,
    )
    out = calculate_pricing(inp_wet)
    # Excess moisture = 4.0; Penalty = 4.0 * 50.0 * 10.0 = 2000.0
    assert out.quote.moisture_penalty_inr == 2000.0
    assert out.quote.net_price_inr == max(0.0, 5000.0 - 2000.0)


def test_biomass_buyer_negotiation_protocol() -> None:
    b_id = uuid.uuid4()
    ord_id = uuid.uuid4()

    # 1. Acceptable offer immediately
    offer_good = BiomassOffer(
        buyer_id=b_id,
        order_id=ord_id,
        proposed_price_per_tonne_inr=1700.0,
        tonnes=100.0,
        delivery_term="ex_field",
    )
    res_good = negotiate_biomass_bid(offer_good)
    assert res_good.accepted is True
    assert res_good.walk_away is False
    assert res_good.counter_price_per_tonne_inr == 1700.0

    # 2. Predatory / unreasonably low offer -> Walk away immediately
    offer_bad = BiomassOffer(
        buyer_id=b_id,
        order_id=ord_id,
        proposed_price_per_tonne_inr=900.0,  # Below 75% of 1600 (1200)
        tonnes=100.0,
        delivery_term="ex_field",
    )
    res_bad = negotiate_biomass_bid(offer_bad)
    assert res_bad.accepted is False
    assert res_bad.walk_away is True

    # 3. Intermediate offer -> Multi-turn counter-offer
    offer_mid = BiomassOffer(
        buyer_id=b_id,
        order_id=ord_id,
        proposed_price_per_tonne_inr=1450.0,
        tonnes=100.0,
        delivery_term="ex_field",
    )
    res_r1 = negotiate_biomass_bid(offer_mid, round_number=1)
    assert res_r1.accepted is False
    assert res_r1.walk_away is False
    assert res_r1.counter_price_per_tonne_inr > 1600.0

    # Round 5 (final round)
    res_r5 = negotiate_biomass_bid(offer_mid, round_number=5, max_rounds=5)
    assert res_r5.walk_away is True  # Buyer did not meet reservation price


def test_contract_drafting_and_sha256_integrity() -> None:
    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()
    b_id = uuid.uuid4()

    draft = draft_contract_terms(
        field_id=fld_id,
        farmer_id=f_id,
        buyer_id=b_id,
        price_per_tonne_inr=1650.0,
        tonnes_agreed=50.0,
        delivery_term="ex_field",
    )

    assert len(draft.contract_sha256) == 64
    assert draft.price_per_tonne_inr == 1650.0
    assert draft.tonnes_agreed == 50.0
    assert "SHA-256" in draft.terms_summary


def test_pricing_negotiation_graph_with_buyer_offer() -> None:
    graph = build_pricing_negotiation_graph()

    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()
    b_id = uuid.uuid4()
    ord_id = uuid.uuid4()

    inp = PricingInput(
        farmer_id=f_id,
        field_id=fld_id,
        landholding_class=LandholdingClass.SMALL,
        service_type=ServiceType.BALING,
        area_acres=3.0,
    )
    buyer_offer = BiomassOffer(
        buyer_id=b_id,
        order_id=ord_id,
        proposed_price_per_tonne_inr=1750.0,  # Acceptable
        tonnes=20.0,
        delivery_term="ex_field",
    )

    state = PricingState(input=inp, buyer_offer=buyer_offer)
    res = graph.invoke(state, config={"configurable": {"thread_id": "pn_pricing_test"}})

    assert res["status"] == "completed"
    assert res["counter_offer"].accepted is True
    assert res["contract_draft"] is not None
    assert res["contract_draft"].price_per_tonne_inr == 1750.0
    assert len(res["contract_draft"].contract_sha256) == 64


# ==============================================================================
# Section: test_mrv.py
# ==============================================================================
from stubbleos.data.models import Approval, AuditLog, Consent, ImpactRecord, MrvEvidence, Plan

"""Unit tests for MRV agent: evidence hashing, tamper detection, database persistence, and audit log."""


import pytest

from stubbleos.agents.mrv.graph import build_mrv_graph
from stubbleos.agents.mrv.logic import generate_mrv_evidence, verify_evidence_tamper
from stubbleos.agents.mrv.schemas import MrvInput, MrvState
from stubbleos.data.models import AuditLog, ImpactRecord, MrvEvidence
from stubbleos.data.repositories import AuditLogRepository, MrvRepository


@pytest.fixture
def mrv_repo(session: Session) -> MrvRepository:
    return MrvRepository(session)


@pytest.fixture
def audit_repo(session: Session) -> AuditLogRepository:
    return AuditLogRepository(session)


def test_mrv_hash_reproducibility() -> None:
    """Verifies that identical inputs yield byte-identical canonical SHA-256 hashes."""
    field_id = uuid.uuid4()
    captured = datetime(2026, 10, 25, 12, 0, 0, tzinfo=IST)

    inp1 = MrvInput(
        field_id=field_id,
        area_acres=10.0,
        season="2026_kharif",
        firms_hotspots_detected=0,
        satellite_cleared_confirmed=True,
        captured_at=captured,
    )
    inp2 = MrvInput(
        field_id=field_id,
        area_acres=10.0,
        season="2026_kharif",
        firms_hotspots_detected=0,
        satellite_cleared_confirmed=True,
        captured_at=captured,
    )

    out1 = generate_mrv_evidence(inp1)
    out2 = generate_mrv_evidence(inp2)

    assert out1.evidence.sha256 == out2.evidence.sha256
    assert len(out1.evidence.sha256) == 64
    assert out1.impact.record_sha256 == out2.impact.record_sha256


def test_mrv_evidence_tamper_detection() -> None:
    """Verifies that tampering with an evidence bundle invalidates its cryptographic signature."""
    field_id = uuid.uuid4()
    captured = datetime(2026, 10, 25, 12, 0, 0, tzinfo=IST)

    inp = MrvInput(
        field_id=field_id,
        area_acres=5.0,
        captured_at=captured,
    )
    out = generate_mrv_evidence(inp)

    # Clean bundle verifies correctly
    assert verify_evidence_tamper(out.evidence) is True

    # Tampered inputs: modify acreage
    tampered_inputs = dict(out.evidence.inputs)
    tampered_inputs["area_acres"] = 999.0
    tampered_bundle = out.evidence.model_copy(update={"inputs": tampered_inputs})
    assert verify_evidence_tamper(tampered_bundle) is False

    # Tampered results: falsely claim burn avoided
    tampered_results = dict(out.evidence.result)
    tampered_results["burn_avoided"] = not tampered_results["burn_avoided"]
    tampered_bundle_2 = out.evidence.model_copy(update={"result": tampered_results})
    assert verify_evidence_tamper(tampered_bundle_2) is False


def test_mrv_impact_record_disclaimer_constraint() -> None:
    """Verifies that impact records strictly contain the required non-registry disclaimer."""
    field_id = uuid.uuid4()
    inp = MrvInput(field_id=field_id, area_acres=4.0)
    out = generate_mrv_evidence(inp)

    assert out.impact.label == "indicative impact record (not registry-verified)"
    assert "not registry-verified" in out.impact.label
    assert out.impact.est_co2e_kg_avoided == pytest.approx(4.0 * 1800.0 * 1.46, abs=1.0)


def test_mrv_graph_database_persistence_and_audit_trail(
    mrv_repo: MrvRepository,
    audit_repo: AuditLogRepository,
) -> None:
    """Verifies LangGraph execution persists evidence, impact, and hash-chained audit log."""
    field_id = uuid.uuid4()
    captured = datetime(2026, 10, 25, 14, 30, tzinfo=IST)

    inp = MrvInput(
        field_id=field_id,
        area_acres=8.5,
        season="2026_kharif",
        captured_at=captured,
    )
    state = MrvState(input=inp)
    graph = build_mrv_graph(mrv_repo=mrv_repo, audit_repo=audit_repo)

    result_state = graph.invoke(state, config={"configurable": {"thread_id": "mrv_db_test"}})
    assert result_state["status"] == "completed"
    assert result_state["persisted_to_db"] is True

    out = result_state["output"]
    assert out.audit_log_id is not None

    # Verify database persistence
    db_evidence = mrv_repo.get_evidence(out.evidence.evidence_id)
    assert db_evidence is not None
    assert db_evidence.field_id == field_id
    assert db_evidence.sha256 == out.evidence.sha256

    db_impact = mrv_repo.get_impact_by_field_season(field_id, "2026_kharif")
    assert db_impact is not None
    assert db_impact.burn_avoided is True
    assert db_impact.label == "indicative impact record (not registry-verified)"

    # Verify audit log chain integrity
    verification = audit_repo.verify_chain()
    assert verification.ok is True
    assert verification.entries_checked >= 1


# ==============================================================================
# Section: test_policy_guard.py
# ==============================================================================
from stubbleos.data.models import Approval, AuditLog, Consent, ImpactRecord, MrvEvidence, Plan

"""Unit tests for Policy & Safety Guard agent."""


from datetime import UTC

import pytest

from stubbleos.agents.policy_guard.graph import build_policy_guard_graph
from stubbleos.agents.policy_guard.logic import (
    check_consent,
    check_contact_hours,
    check_pii_leak,
    check_price_bounds,
    evaluate_policy,
)
from stubbleos.agents.policy_guard.schemas import (
    PolicyCheckRequest,
    PolicyGuardState,
)
from stubbleos.agents.policy_guard.tools import create_policy_guard_tools
from stubbleos.core.types import ConsentPurpose
from stubbleos.data.models import Consent
from stubbleos.data.repositories import ConsentRepository


@pytest.fixture
def consent_repo(session: Session) -> ConsentRepository:
    return ConsentRepository(session)


def test_consent_rule(consent_repo: ConsentRepository) -> None:
    farmer_id = uuid.uuid4()
    now_utc = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)

    # 1. No consent recorded -> should fail
    ok, detail = check_consent(
        farmer_id=farmer_id,
        purpose=ConsentPurpose.OUTREACH,
        channel=Channel.WHATSAPP,
        at=now_utc,
        consent_repo=consent_repo,
    )
    assert not ok
    assert "has not granted valid consent" in (detail or "")

    # 2. Grant consent -> should pass
    consent_repo.record(
        farmer_id=farmer_id,
        purpose=ConsentPurpose.OUTREACH,
        channel=Channel.WHATSAPP,
        granted=True,
        language=Language.PUNJABI,
        at=now_utc - timedelta(hours=1),
        recorded_by="tester",
    )
    ok, detail = check_consent(
        farmer_id=farmer_id,
        purpose=ConsentPurpose.OUTREACH,
        channel=Channel.WHATSAPP,
        at=now_utc,
        consent_repo=consent_repo,
    )
    assert ok
    assert detail is None

    # 3. Revoke consent -> should fail
    consent_repo.record(
        farmer_id=farmer_id,
        purpose=ConsentPurpose.OUTREACH,
        channel=Channel.WHATSAPP,
        granted=False,
        language=Language.PUNJABI,
        at=now_utc + timedelta(minutes=5),
        recorded_by="tester",
    )
    ok, detail = check_consent(
        farmer_id=farmer_id,
        purpose=ConsentPurpose.OUTREACH,
        channel=Channel.WHATSAPP,
        at=now_utc + timedelta(minutes=10),
        consent_repo=consent_repo,
    )
    assert not ok


def test_price_bounds_rule() -> None:
    bounds = (1500.0, 2500.0)

    # Within bounds -> pass
    ok, detail = check_price_bounds(1800.0, bounds)
    assert ok
    assert detail is None

    # Exact boundary -> pass
    ok_min, _ = check_price_bounds(1500.0, bounds)
    ok_max, _ = check_price_bounds(2500.0, bounds)
    assert ok_min
    assert ok_max

    # Below floor -> fail
    ok_low, detail_low = check_price_bounds(1400.0, bounds)
    assert not ok_low
    assert "outside allowable bounds" in (detail_low or "")

    # Above ceiling -> fail
    ok_high, detail_high = check_price_bounds(2600.0, bounds)
    assert not ok_high
    assert "outside allowable bounds" in (detail_high or "")


def test_pii_leak_rule() -> None:
    # Clean text -> pass
    ok, detail = check_pii_leak("Machine dispatch scheduled for tomorrow morning.", None)
    assert ok
    assert detail is None

    # Indian phone number leak -> fail
    ok_phone, detail_phone = check_pii_leak("Contact driver at +91 9876543210 for pickup.", None)
    assert not ok_phone
    assert "unredacted phone number" in (detail_phone or "")

    # 10-digit raw mobile -> fail
    ok_raw, _ = check_pii_leak("Call 9123456789", None)
    assert not ok_raw

    # Aadhaar number leak -> fail
    ok_aadhaar, detail_aadhaar = check_pii_leak("Farmer Aadhaar: 1234 5678 9012", None)
    assert not ok_aadhaar
    assert "unredacted Aadhaar number" in (detail_aadhaar or "")

    # Email address leak -> fail
    ok_email, detail_email = check_pii_leak("Send invoice to farmer@example.com", None)
    assert not ok_email
    assert "unredacted email address" in (detail_email or "")


def test_allowed_contact_hours_ist() -> None:
    # Allowed hours: 08:00 to 19:00 IST
    # 12:00 IST -> UTC is 06:30 -> should pass
    dt_valid = datetime(2026, 10, 20, 12, 0, tzinfo=IST)
    ok, detail = check_contact_hours(dt_valid, 8, 19)
    assert ok
    assert detail is None

    # 04:00 IST (early morning) -> should fail
    dt_early = datetime(2026, 10, 20, 4, 30, tzinfo=IST)
    ok_early, detail_early = check_contact_hours(dt_early, 8, 19)
    assert not ok_early
    assert "outside allowed window" in (detail_early or "")

    # 22:30 IST (late night) -> should fail
    dt_late = datetime(2026, 10, 20, 22, 30, tzinfo=IST)
    ok_late, detail_late = check_contact_hours(dt_late, 8, 19)
    assert not ok_late
    assert "outside allowed window" in (detail_late or "")


def test_evaluate_policy_comprehensive(consent_repo: ConsentRepository) -> None:
    farmer_id = uuid.uuid4()
    now_ist = datetime(2026, 10, 20, 11, 0, tzinfo=IST)
    consent_repo.record(
        farmer_id=farmer_id,
        purpose=ConsentPurpose.OUTREACH,
        channel=Channel.WHATSAPP,
        granted=True,
        language=Language.PUNJABI,
        at=now_ist - timedelta(hours=1),
        recorded_by="tester",
    )

    req_valid = PolicyCheckRequest(
        action_ref="action_1",
        farmer_id=farmer_id,
        purpose=ConsentPurpose.OUTREACH,
        channel=Channel.WHATSAPP,
        timestamp=now_ist,
        proposed_price_inr_per_tonne=1900.0,
        price_bounds=(1500.0, 2500.0),
        message_text="Residue clearance confirmed for tomorrow.",
    )
    res_valid = evaluate_policy(req_valid, consent_repo=consent_repo)
    assert res_valid.is_allowed
    assert len(res_valid.violations) == 0

    # Violate price and PII
    req_invalid = req_valid.model_copy(
        update={
            "proposed_price_inr_per_tonne": 3500.0,
            "message_text": "Call me at 9876543210 to discuss ₹3500 rate",
        }
    )
    res_invalid = evaluate_policy(req_invalid, consent_repo=consent_repo)
    assert not res_invalid.is_allowed
    assert len(res_invalid.violations) == 2
    rule_ids = {v.rule_id for v in res_invalid.violations}
    assert "PRICE_OUT_OF_BOUNDS" in rule_ids
    assert "PII_LEAK_DETECTED" in rule_ids


def test_policy_guard_graph(consent_repo: ConsentRepository) -> None:
    graph = build_policy_guard_graph(consent_repo=consent_repo)

    req = PolicyCheckRequest(
        action_ref="graph_test",
        timestamp=datetime(2026, 10, 20, 14, 0, tzinfo=IST),
        message_text="Approved field work.",
    )
    state = PolicyGuardState(request=req)
    result_state = graph.invoke(state, config={"configurable": {"thread_id": "test_pg"}})

    assert result_state["is_allowed"] is True
    assert result_state["result"] is not None


def test_policy_guard_tools(consent_repo: ConsentRepository) -> None:
    tools = create_policy_guard_tools(consent_repo=consent_repo)
    assert len(tools) == 4

    scan_tool = next(t for t in tools if t.name == "scan_for_pii")
    clean_res = scan_tool.invoke({"text": "Hello world"})
    assert clean_res["is_clean"] is True

    pii_res = scan_tool.invoke({"text": "Call 9876543210"})
    assert pii_res["is_clean"] is False


def test_policy_guard_failure_mode_bad_data() -> None:
    """Failure-mode test: Malformed request payload fails strict validation."""
    with pytest.raises(ValidationError):
        PolicyCheckRequest(
            action_ref="bad_action",
            extra_illegal_field="should_fail",  # type: ignore[call-arg]
        )


# ==============================================================================
# Section: test_agent_orchestrator.py
# ==============================================================================
from stubbleos.data.models import Approval, AuditLog, Consent, ImpactRecord, MrvEvidence, Plan

"""Comprehensive scenario tests for Orchestrator (supervisor) agent."""


import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from stubbleos.agents.orchestrator.graph import build_orchestrator_graph
from stubbleos.agents.orchestrator.logic import (
    handle_replan_event,
    resolve_conflicts,
)
from stubbleos.agents.orchestrator.schemas import (
    DistrictPlan,
    OrchestratorState,
)
from stubbleos.core.events import (
    ReplanTriggered,
)
from stubbleos.core.ids import SeededUUIDFactory
from stubbleos.core.types import (
    ApprovalStatus,
    PlanStatus,
)
from stubbleos.data.models import Approval, Consent, Plan
from stubbleos.data.repositories import (
    PlanRepository,
)


@pytest.fixture
def plan_repo(session: Session) -> PlanRepository:
    return PlanRepository(session)


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus(id_factory=SeededUUIDFactory(42))


@pytest.fixture
def test_data() -> tuple[list[JobRequest], list[MachineResource]]:
    jobs = [
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.MARGINAL,
            area_acres=2.0,
            earliest_start_hour=0.0,
            deadline_hour=48.0,
            center_lat=30.25,
            center_lon=75.80,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=3.5,
            earliest_start_hour=0.0,
            deadline_hour=72.0,
            center_lat=30.28,
            center_lon=75.83,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
    ]
    machines = [
        MachineResource(
            machine_id=uuid.uuid4(),
            machine_type=MachineType.HAPPY_SEEDER,
            capacity_acres_per_hour=1.5,
            hourly_cost_inr=800.0,
            current_lat=30.24,
            current_lon=75.79,
            available_from_hour=0.0,
        )
    ]
    return jobs, machines


@pytest.mark.asyncio
async def test_orchestrator_normal_flow(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    jobs, machines = test_data
    fake_llm = FakeLLM(default="Plan executed cleanly.")

    graph = build_orchestrator_graph(
        llm=fake_llm,
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=MemorySaver(),
    )

    state = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        confidence_threshold=0.50,
    )

    config = {"configurable": {"thread_id": "orch_normal_1"}}
    res = await graph.ainvoke(state, config=config)

    assert res["status"] == "completed"
    plan = res["plan"]
    assert plan is not None
    assert plan.district == "Sangrur"
    assert plan.version == 1
    assert len(plan.assignments) > 0

    # Verify database persistence
    saved_plan = plan_repo.get_by_id(plan.plan_id)
    assert saved_plan is not None
    assert saved_plan.status == PlanStatus.ACTIVE

    # Verify event publication
    plan_events = event_bus.of_type("plan.created")
    assert len(plan_events) >= 1


@pytest.mark.asyncio
async def test_scenario_rain_shock_triggers_replan(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    """Scenario 1: Rain forecast shock accelerates deadlines, versions plan (v1 -> v2), and supersedes v1."""
    jobs, machines = test_data
    graph = build_orchestrator_graph(
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=MemorySaver(),
    )

    # Day 1: Initial plan (v1)
    state_v1 = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        confidence_threshold=0.50,
    )
    res_v1 = await graph.ainvoke(state_v1, config={"configurable": {"thread_id": "thread_rain_1"}})
    plan_v1: DistrictPlan = res_v1["plan"]
    assert plan_v1.version == 1

    # Rain shock event occurs!
    rain_event = ReplanTriggered(
        district="Sangrur",
        reason=ReplanReason.RAIN_FORECAST_CHANGE,
        details={"deadline_compression_hours": "12.0"},
    )

    # Replanning invocation with replan_trigger and previous_plan
    state_v2 = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        replan_trigger=rain_event,
        previous_plan=plan_v1,
        confidence_threshold=0.50,
    )
    res_v2 = await graph.ainvoke(state_v2, config={"configurable": {"thread_id": "thread_rain_2"}})
    plan_v2: DistrictPlan = res_v2["plan"]

    assert plan_v2.version == 2
    assert plan_v2.parent_plan_id == plan_v1.plan_id

    # Verify plan_v1 is marked SUPERSEDED in database
    db_plan_v1 = plan_repo.get_by_id(plan_v1.plan_id)
    assert db_plan_v1 is not None
    assert db_plan_v1.status == PlanStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_scenario_machine_breakdown_replan(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    """Scenario 2: Machine breakdown triggers reassignment and machine removal."""
    jobs, machines = test_data
    broken_machine_id = machines[0].machine_id

    # Add a backup machine so assignments can still be fulfilled
    backup_machine = MachineResource(
        machine_id=uuid.uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.2,
        hourly_cost_inr=850.0,
        current_lat=30.27,
        current_lon=75.81,
        available_from_hour=0.0,
    )
    fleet = [machines[0], backup_machine]

    breakdown_event = ReplanTriggered(
        district="Sangrur",
        reason=ReplanReason.MACHINE_BREAKDOWN,
        details={"machine_id": str(broken_machine_id)},
    )

    graph = build_orchestrator_graph(
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=MemorySaver(),
    )

    state = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=fleet,
        replan_trigger=breakdown_event,
        confidence_threshold=0.50,
    )

    res = await graph.ainvoke(state, config={"configurable": {"thread_id": "thread_breakdown"}})
    plan = res["plan"]
    assert plan is not None

    # Verify no assignment was given to the broken machine
    for a in plan.assignments:
        assert a.machine_id != broken_machine_id
        assert a.machine_id == backup_machine.machine_id


@pytest.mark.asyncio
async def test_scenario_burn_detected_replan(
    test_data: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    """Scenario 3: Stubble burn detected removes burnt field from active jobs."""
    jobs, machines = test_data
    burnt_field_id = jobs[0].field_id

    burn_event = ReplanTriggered(
        district="Sangrur",
        reason=ReplanReason.BURN_DETECTED,
        details={"field_id": str(burnt_field_id)},
    )

    filtered_jobs, _ = handle_replan_event(burn_event, jobs, machines)
    remaining_ids = {j.field_id for j in filtered_jobs}
    assert burnt_field_id not in remaining_ids
    assert len(filtered_jobs) == len(jobs) - 1


def test_orchestrator_conflict_resolution_smallholder_priority(
    test_data: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    """Scenario 4: Resolves competing claims prioritizing marginal/smallholders."""
    jobs, machines = test_data
    winner, tb_log = resolve_conflicts(jobs, machines[0], current_hour=0.0)

    assert winner is not None
    # Marginal farmer has earlier deadline (36h vs 48h) and smallholder status
    assert winner.field_id == jobs[0].field_id
    assert tb_log.winning_job_id == jobs[0].field_id


@pytest.mark.asyncio
async def test_scenario_hitl_low_confidence_interrupt_and_resume(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    """Scenario 5: Low confidence triggers LangGraph interrupt, writes Approval, and resumes upon approval."""
    jobs, machines = test_data
    checkpointer = MemorySaver()

    graph = build_orchestrator_graph(
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=checkpointer,
    )

    state = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        force_interrupt=True,
    )

    config = {"configurable": {"thread_id": "hitl_thread_1"}}

    # Step 1: Invocation halts at interrupt
    interrupted_state = await graph.ainvoke(state, config=config)
    assert "__interrupt__" in interrupted_state
    interrupt_payload = interrupted_state["__interrupt__"][0].value
    assert "approval_id" in interrupt_payload

    approval_id = uuid.UUID(interrupt_payload["approval_id"])

    # Verify pending Approval in database repository
    pending_appr = approval_repo.get_by_id(approval_id)
    assert pending_appr is not None
    assert pending_appr.status == ApprovalStatus.PENDING

    # Verify ApprovalRequested event
    appr_events = event_bus.of_type("approval.requested")
    assert len(appr_events) >= 1

    # Step 2: Coordinator approves and graph resumes
    resumed_state = await graph.ainvoke(
        Command(resume={"status": "approved", "decided_by_role": "fpo_coordinator"}),
        config=config,
    )

    assert resumed_state["status"] == "completed"
    assert resumed_state["plan"] is not None

    # Verify resolved Approval in database
    resolved_appr = approval_repo.get_by_id(approval_id)
    assert resolved_appr is not None
    assert resolved_appr.status == ApprovalStatus.APPROVED

    # Verify ApprovalResolved event
    resolved_events = event_bus.of_type("approval.resolved")
    assert len(resolved_events) >= 1


@pytest.mark.asyncio
async def test_scenario_hitl_rejection(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    """Scenario 6: Coordinator rejects low-confidence plan; plan is aborted."""
    jobs, machines = test_data
    checkpointer = MemorySaver()

    graph = build_orchestrator_graph(
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=checkpointer,
    )

    state = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        force_interrupt=True,
    )

    config = {"configurable": {"thread_id": "hitl_thread_reject"}}

    # Step 1: Halts at interrupt
    await graph.ainvoke(state, config=config)

    # Step 2: Coordinator rejects
    resumed_state = await graph.ainvoke(
        Command(resume={"status": "rejected", "decided_by_role": "fpo_coordinator"}),
        config=config,
    )

    assert resumed_state["approval_status"] == ApprovalStatus.REJECTED
    assert resumed_state.get("plan") is None


# ==============================================================================
# Section: test_agent_skeletons.py
# ==============================================================================
"""Unit tests for skeleton agents (Field Monitor, Weather Window, Farmer Voice, Pricing, MRV)."""


import pytest

from stubbleos.agents.farmer_voice.tools import create_farmer_voice_tools
from stubbleos.agents.field_monitor.logic import detect_field_states
from stubbleos.agents.field_monitor.tools import create_field_monitor_tools
from stubbleos.agents.mrv.logic import compute_mrv_evidence
from stubbleos.agents.mrv.tools import create_mrv_tools
from stubbleos.agents.pricing_negotiation.tools import create_pricing_tools
from stubbleos.agents.weather_window.tools import create_weather_tools


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


# ==============================================================================
# Section: test_agent_events_contract.py
# ==============================================================================
"""Contract tests for typed agent event payloads."""


from stubbleos.core.events import (
    ApprovalRequested,
    ApprovalResolved,
    BurnDetected,
    Event,
    MachineBreakdown,
    PlanCreated,
    PolicyViolationDetected,
)


def test_event_contracts_serialization_and_deserialization() -> None:
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

    # 1. PlanCreated
    plan_id = uuid.uuid4()
    p1 = PlanCreated(
        plan_id=plan_id,
        district="Sangrur",
        strategy="centralized",
        fields_assigned=10,
        fields_unassigned=2,
    )
    e1 = Event.create(p1, source="orchestrator", ts=now, district="Sangrur")
    rec1 = e1.typed_payload()
    assert isinstance(rec1, PlanCreated)
    assert rec1.plan_id == plan_id
    assert rec1.fields_assigned == 10

    # 2. ApprovalRequested & ApprovalResolved
    appr_id = uuid.uuid4()
    p2 = ApprovalRequested(
        approval_id=appr_id,
        kind="plan_confidence",
        subject_id=plan_id,
        reason="Coverage 0.45 below threshold",
        confidence=0.45,
    )
    e2 = Event.create(p2, source="orchestrator", ts=now)
    rec2 = e2.typed_payload()
    assert isinstance(rec2, ApprovalRequested)
    assert rec2.confidence == 0.45

    p3 = ApprovalResolved(
        approval_id=appr_id,
        status=ApprovalStatus.APPROVED,
        decided_by_role="fpo_coordinator",
    )
    e3 = Event.create(p3, source="orchestrator", ts=now)
    rec3 = e3.typed_payload()
    assert isinstance(rec3, ApprovalResolved)
    assert rec3.status == ApprovalStatus.APPROVED

    # 3. ReplanTriggered
    p4 = ReplanTriggered(
        district="Sangrur",
        reason=ReplanReason.RAIN_FORECAST_CHANGE,
        details={"deadline_compression_hours": "24.0"},
    )
    e4 = Event.create(p4, source="weather_window", ts=now, district="Sangrur")
    rec4 = e4.typed_payload()
    assert isinstance(rec4, ReplanTriggered)
    assert rec4.reason == ReplanReason.RAIN_FORECAST_CHANGE

    # 4. PolicyViolationDetected
    p5 = PolicyViolationDetected(
        rule_id="CONSENT_REQUIRED",
        severity="blocking",
        action_ref="farmer_outreach_123",
        detail="Missing consent for outreach on whatsapp",
    )
    e5 = Event.create(p5, source="policy_guard", ts=now)
    rec5 = e5.typed_payload()
    assert isinstance(rec5, PolicyViolationDetected)
    assert rec5.severity == "blocking"

    # 5. MachineBreakdown & BurnDetected
    m_id = uuid.uuid4()
    p6 = MachineBreakdown(machine_id=m_id, expected_repair_days=2.5)
    e6 = Event.create(p6, source="machine_scheduler", ts=now)
    rec6 = e6.typed_payload()
    assert isinstance(rec6, MachineBreakdown)
    assert rec6.machine_id == m_id

    f_id = uuid.uuid4()
    p7 = BurnDetected(
        field_id=f_id,
        detected_at=now,
        source="firms",
        confidence=0.95,
    )
    e7 = Event.create(p7, source="field_monitor", ts=now)
    rec7 = e7.typed_payload()
    assert isinstance(rec7, BurnDetected)
    assert rec7.source == "firms"


# ==============================================================================
# Section: test_agent_failure_modes.py
# ==============================================================================
"""Failure mode tests for every StubbleOS agent (bad data, timeouts, low confidence)."""


import pytest

from stubbleos.agents.orchestrator.logic import calculate_plan_confidence
from stubbleos.agents.orchestrator.schemas import OrchestratorInput


def test_failure_mode_orchestrator_bad_data() -> None:
    """Orchestrator failure mode: Malformed input data rejected by strict schema."""
    with pytest.raises(ValidationError):
        OrchestratorInput(
            district="Sangrur",
            plan_date=date(2026, 10, 20),
            illegal_field_name="forbidden_payload",  # type: ignore[call-arg]
        )


def test_failure_mode_orchestrator_low_confidence_detection() -> None:
    """Orchestrator failure mode: Extreme machine shortage produces low confidence score."""
    # 10 jobs pending, 0 assigned, solver infeasible -> confidence should be severely penalized
    conf = calculate_plan_confidence(
        assignments=[],
        total_jobs=10,
        solver_status="INFEASIBLE",
    )
    assert conf < 0.30


@pytest.mark.asyncio
async def test_failure_mode_machine_scheduler_timeout() -> None:
    """Machine Scheduler failure mode: Short time limit yields best feasible or fallback without crashing."""
    jobs = [
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=48.0,
            center_lat=30.25,
            center_lon=75.80,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        )
    ]
    machines = [
        MachineResource(
            machine_id=uuid.uuid4(),
            machine_type=MachineType.HAPPY_SEEDER,
            capacity_acres_per_hour=1.5,
            hourly_cost_inr=800.0,
            current_lat=30.24,
            current_lon=75.79,
            available_from_hour=0.0,
        )
    ]
    # Ultra-short timeout (0.001s / 1ms)
    cfg = SchedulerConfig(time_limit_seconds=0.001)
    inp = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="cpsat",
        config=cfg,
        request_explanation=False,
    )
    output = await run_machine_scheduler(inp)
    # Solver must return gracefully with status indicator
    assert output.solver_status in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "FALLBACK_GREEDY"}


def test_failure_mode_machine_scheduler_bad_data() -> None:
    """Machine Scheduler failure mode: Invalid machine type rejected."""
    with pytest.raises(ValidationError):
        MachineSchedulerInput(
            jobs=[],
            machines=[],
            mode="invalid_algorithm",  # type: ignore[arg-type]
        )


def test_failure_mode_logistics_bad_data() -> None:
    """Logistics failure mode: Missing required fields rejected."""
    with pytest.raises(ValidationError):
        LogisticsInput()  # type: ignore[call-arg]


def test_failure_mode_buyer_demand_bad_data() -> None:
    """Buyer Demand failure mode: Extra unknown fields rejected."""
    with pytest.raises(ValidationError):
        BuyerDemandInput(district="Sangrur", unknown_key=True)  # type: ignore[call-arg]


def test_failure_mode_policy_guard_bad_data() -> None:
    """Policy Guard failure mode: Extra attributes rejected."""
    with pytest.raises(ValidationError):
        PolicyCheckRequest(action_ref="act_1", invalid_prop="fail")  # type: ignore[call-arg]


def test_failure_mode_field_monitor_bad_data() -> None:
    """Field Monitor failure mode: Negative observation window rejected if constrained or invalid type."""
    with pytest.raises(ValidationError):
        FieldMonitorInput(district="Sangrur", field_ids=["not-a-uuid"])  # type: ignore[list-item]


def test_failure_mode_weather_window_bad_data() -> None:
    """Weather Window failure mode: Invalid date format rejected."""
    with pytest.raises(ValidationError):
        WeatherWindowInput(district="Sangrur", start_date="bad_date", end_date="bad_date")  # type: ignore[arg-type]


def test_failure_mode_farmer_voice_bad_data() -> None:
    """Farmer Voice failure mode: Invalid farmer ID rejected."""
    with pytest.raises(ValidationError):
        FarmerVoiceInput(farmer_id="bad-uuid", inbound_text="hello")  # type: ignore[arg-type]


def test_failure_mode_pricing_negotiation_bad_data() -> None:
    """Pricing Negotiation failure mode: Negative area rejected."""
    with pytest.raises(ValidationError):
        PricingInput(
            farmer_id=uuid.uuid4(),
            field_id=uuid.uuid4(),
            landholding_class=LandholdingClass.MARGINAL,
            service_type=ServiceType.IN_SITU_SOWING,
            area_acres=-2.5,
        )


def test_failure_mode_mrv_bad_data() -> None:
    """MRV failure mode: Non-positive area rejected."""
    with pytest.raises(ValidationError):
        MrvInput(field_id=uuid.uuid4(), area_acres=0.0)


# ==============================================================================
# Section: test_scheduler.py
# ==============================================================================
"""Unit tests for the CP-SAT machine scheduler model."""

from uuid import uuid4

from stubbleos.optimization.scheduler import (
    solve_schedule,
)


def test_scheduler_one_job_at_a_time_no_overlap() -> None:
    m_id = uuid4()
    machine = MachineResource(
        machine_id=m_id,
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.0,
        hourly_cost_inr=1800.0,
        current_lat=30.8,
        current_lon=75.8,
        available_from_hour=0.0,
    )

    # 3 jobs of 5 acres each -> 5 hours each
    jobs = [
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=5.0,
            earliest_start_hour=0.0,
            deadline_hour=50.0,
            center_lat=30.81,
            center_lon=75.81,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=5.0,
            earliest_start_hour=0.0,
            deadline_hour=50.0,
            center_lat=30.82,
            center_lon=75.82,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=5.0,
            earliest_start_hour=0.0,
            deadline_hour=50.0,
            center_lat=30.83,
            center_lon=75.83,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
    ]

    out = solve_schedule(jobs=jobs, machines=[machine])
    assert out.solver_status in ("OPTIMAL", "FEASIBLE")
    assert len(out.assignments) == 3

    # Verify no overlaps between consecutive intervals on the same machine
    sorted_a = sorted(out.assignments, key=lambda a: a.start_hour)
    for i in range(len(sorted_a) - 1):
        assert sorted_a[i].end_hour <= sorted_a[i + 1].start_hour + 1e-4


def test_scheduler_readiness_window_constraint() -> None:
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.SUPER_SEEDER,
        capacity_acres_per_hour=1.5,
        hourly_cost_inr=2000.0,
        current_lat=30.8,
        current_lon=75.8,
        available_from_hour=0.0,
    )

    # Field only ready at hour 20.0
    job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.MEDIUM,
        area_acres=6.0,
        earliest_start_hour=20.0,
        deadline_hour=40.0,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )

    out = solve_schedule(jobs=[job], machines=[machine])
    assert len(out.assignments) == 1
    assert out.assignments[0].start_hour >= 20.0 - 1e-4


def test_scheduler_fairness_priority_under_contention() -> None:
    # 1 machine available, 2 contending jobs with same deadline and same size
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.BALER,
        capacity_acres_per_hour=2.0,
        hourly_cost_inr=2500.0,
        current_lat=30.8,
        current_lon=75.8,
        available_from_hour=0.0,
    )

    # Tight deadline where only 1 job can be served on time
    marginal_job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.MARGINAL,
        area_acres=4.0,  # 2.0 hrs
        earliest_start_hour=0.0,
        deadline_hour=2.5,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.BALER],
    )
    large_job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.LARGE,
        area_acres=4.0,  # 2.0 hrs
        earliest_start_hour=0.0,
        deadline_hour=2.5,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.BALER],
    )

    out = solve_schedule(jobs=[marginal_job, large_job], machines=[machine])
    assert len(out.assignments) >= 1
    # Marginal farmer must be selected for on-time clearance due to fairness weighting
    on_time_assignments = [a for a in out.assignments if a.is_on_time]
    assert len(on_time_assignments) == 1
    assert on_time_assignments[0].field_id == marginal_job.field_id


def test_scheduler_monotonicity_adding_machine_never_decreases_objective() -> None:
    m1 = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.0,
        hourly_cost_inr=1800.0,
        current_lat=30.8,
        current_lon=75.8,
    )
    m2 = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.0,
        hourly_cost_inr=1800.0,
        current_lat=30.81,
        current_lon=75.81,
    )

    jobs = [
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=10.0,
            center_lat=30.8,
            center_lon=75.8,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=10.0,
            center_lat=30.81,
            center_lon=75.81,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
    ]

    out_1 = solve_schedule(jobs=jobs, machines=[m1])
    out_2 = solve_schedule(jobs=jobs, machines=[m1, m2])

    assert out_2.objective_value >= out_1.objective_value - 1e-4
    assert len(out_2.assignments) >= len(out_1.assignments)


def test_scheduler_time_limit_greedy_fallback() -> None:
    # A tiny time limit (0.001s) forces timeout fallback
    cfg = SchedulerConfig(time_limit_seconds=0.0001)
    m = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.SUPER_SEEDER,
        capacity_acres_per_hour=1.5,
        hourly_cost_inr=2000.0,
        current_lat=30.8,
        current_lon=75.8,
    )
    job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SMALL,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )

    out = solve_schedule(jobs=[job], machines=[m], config=cfg)
    assert out.solver_status in ("OPTIMAL", "FEASIBLE", "FALLBACK_GREEDY")
    assert len(out.assignments) == 1
    assert out.assignments[0].field_id == job.field_id


# ==============================================================================
# Section: test_routing.py
# ==============================================================================
"""Unit tests for the OR-Tools VRP routing model and distance matrix providers."""


from stubbleos.optimization.routing import (
    HaversineDistanceMatrixProvider,
    OSRMClient,
    solve_straw_routing,
)


def test_haversine_distance_matrix_provider() -> None:
    provider = HaversineDistanceMatrixProvider()
    locs = [(30.8, 75.8), (30.85, 75.85), (30.9, 75.9)]

    dist_mat, dur_mat = provider.get_distance_and_duration_matrix(locs, speed_kmh=40.0)

    assert len(dist_mat) == 3
    assert len(dur_mat) == 3
    assert dist_mat[0][0] == 0.0
    assert dist_mat[0][1] > 0.0
    # Symmetry
    assert abs(dist_mat[0][1] - dist_mat[1][0]) < 1e-4
    assert dur_mat[0][1] == dist_mat[0][1] / 40.0


def test_osrm_client_fallback_to_haversine_when_offline() -> None:
    # Pointing to a dead port triggers the transparent haversine fallback
    client = OSRMClient(base_url="http://127.0.0.1:59999", timeout_seconds=0.1)
    locs = [(30.8, 75.8), (30.85, 75.85)]

    dist_mat, _dur_mat = client.get_distance_and_duration_matrix(locs)
    assert len(dist_mat) == 2
    assert dist_mat[0][1] > 0.0


def test_straw_routing_truck_capacity_constraint() -> None:
    truck = TruckSpec(
        truck_id=uuid4(),
        capacity_tonnes=10.0,
        cost_per_km_inr=45.0,
        co2_kg_per_km=1.42,
        depot_lat=30.8,
        depot_lon=75.8,
    )
    buyer = BuyerDropoff(
        buyer_id=uuid4(),
        lat=30.9,
        lon=75.9,
        max_moisture_pct=16.0,
        capacity_tonnes=100.0,
    )
    # Field with 15 tonnes (exceeds single 10-tonne truck capacity)
    pickup = FieldPickup(
        field_id=uuid4(),
        lat=30.82,
        lon=75.82,
        tonnes=15.0,
        moisture_pct=14.0,
        deadline_hour=50.0,
    )

    out = solve_straw_routing(pickups=[pickup], dropoffs=[buyer], trucks=[truck])
    assert len(out.routes) == 1
    route = out.routes[0]
    assert route.delivered_tonnes <= truck.capacity_tonnes
    assert route.delivered_tonnes == 10.0


def test_straw_routing_moisture_spec_filtering() -> None:
    truck = TruckSpec(
        truck_id=uuid4(),
        capacity_tonnes=10.0,
        cost_per_km_inr=45.0,
        co2_kg_per_km=1.42,
        depot_lat=30.8,
        depot_lon=75.8,
    )
    # Biomass buyer with strict 16% max moisture
    buyer = BuyerDropoff(
        buyer_id=uuid4(),
        lat=30.9,
        lon=75.9,
        max_moisture_pct=16.0,
        capacity_tonnes=50.0,
    )
    # Field with wet straw at 24% moisture (exceeds buyer threshold)
    wet_pickup = FieldPickup(
        field_id=uuid4(),
        lat=30.82,
        lon=75.82,
        tonnes=8.0,
        moisture_pct=24.0,
        deadline_hour=50.0,
    )

    out = solve_straw_routing(pickups=[wet_pickup], dropoffs=[buyer], trucks=[truck])
    assert len(out.routes) == 0
    assert wet_pickup.field_id in out.unserved_field_ids
    assert out.solver_status == "ALL_PICKUPS_EXCEED_MOISTURE"


# ==============================================================================
# Section: test_auction_conflicts.py
# ==============================================================================
"""Unit tests for contract-net auctions and conflict resolution policy."""


import pytest

from stubbleos.coordination.auction import ContractNetCoordinator, TaskAnnouncement
from stubbleos.coordination.conflicts import ConflictResolver, TieBreakCriterion


def test_contract_net_auction_flow() -> None:
    coord = ContractNetCoordinator(seed=42)

    task = TaskAnnouncement(
        task_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SMALL,
        area_acres=4.0,
        center_lat=30.8,
        center_lon=75.8,
        earliest_start_hour=0.0,
        deadline_hour=24.0,
        eligible_machine_types=[MachineType.HAPPY_SEEDER],
    )

    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.2,
        hourly_cost_inr=1800.0,
        current_lat=30.81,
        current_lon=75.81,
        available_from_hour=0.0,
    )

    result = coord.run_auction_round(tasks=[task], machines=[machine], current_hour=0.0)

    assert result.round_number == 1
    assert result.announcements_count == 1
    assert result.bids_count == 1
    assert len(result.awards) == 1

    award = result.awards[0]
    assert award.task_id == task.task_id
    assert award.machine_id == machine.machine_id
    assert award.is_on_time is True
    assert award.agreed_price_inr > 0.0


def test_conflict_resolution_smallholder_priority() -> None:
    resolver = ConflictResolver(seed=100)
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.SUPER_SEEDER,
        capacity_acres_per_hour=1.5,
        hourly_cost_inr=2000.0,
        current_lat=30.8,
        current_lon=75.8,
    )

    small_job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.MARGINAL,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=48.0,  # Urgent smallholder
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )
    large_job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.LARGE,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=48.0,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )

    winner, log = resolver.resolve_competition([small_job, large_job], machine, current_hour=0.0)
    assert winner.field_id == small_job.field_id
    assert log.criterion_applied == TieBreakCriterion.FAIRNESS_SMALLHOLDER_PRIORITY
    assert log.winning_job_id == small_job.field_id
    assert len(resolver.audit_log) == 1


def test_conflict_resolution_deadline_urgency_and_tie_breaking() -> None:
    resolver = ConflictResolver(seed=42)
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.BALER,
        capacity_acres_per_hour=2.0,
        hourly_cost_inr=2400.0,
        current_lat=30.8,
        current_lon=75.8,
    )

    job_urgent = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,  # More urgent
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.BALER],
    )
    job_relaxed = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=60.0,  # Less urgent
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.BALER],
    )

    winner, log = resolver.resolve_competition([job_urgent, job_relaxed], machine, current_hour=0.0)
    assert winner.field_id == job_urgent.field_id
    assert log.criterion_applied == TieBreakCriterion.DEADLINE_URGENCY


def test_conflict_resolution_distance_and_deterministic_hash() -> None:
    resolver = ConflictResolver(seed=42)
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.BALER,
        capacity_acres_per_hour=2.0,
        hourly_cost_inr=2400.0,
        current_lat=30.8,
        current_lon=75.8,
    )

    # 1. Distance proximity test
    job_near = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.81,  # near (~1.1 km)
        center_lon=75.81,
        eligible_machine_types=[MachineType.BALER],
    )
    job_far = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.95,  # far (>15 km)
        center_lon=75.95,
        eligible_machine_types=[MachineType.BALER],
    )
    winner_dist, log_dist = resolver.resolve_competition([job_near, job_far], machine, current_hour=0.0)
    assert winner_dist.field_id == job_near.field_id
    assert log_dist.criterion_applied == TieBreakCriterion.DISTANCE_PROXIMITY

    # 2. Deterministic hash tie-break test (identical lat, lon, deadline, class)
    job_tie_1 = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.81,
        center_lon=75.81,
        eligible_machine_types=[MachineType.BALER],
    )
    job_tie_2 = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.81,
        center_lon=75.81,
        eligible_machine_types=[MachineType.BALER],
    )
    winner_hash, log_hash = resolver.resolve_competition([job_tie_1, job_tie_2], machine, current_hour=0.0)
    assert winner_hash.field_id in (job_tie_1.field_id, job_tie_2.field_id)
    assert log_hash.criterion_applied == TieBreakCriterion.DETERMINISTIC_SEED_HASH

    # 3. Single candidate job
    winner_single, _log_single = resolver.resolve_competition([job_near], machine, current_hour=0.0)
    assert winner_single.field_id == job_near.field_id

    # 4. Empty candidate job list raises ValueError
    with pytest.raises(ValueError, match="Cannot resolve empty list"):
        resolver.resolve_competition([], machine, current_hour=0.0)


# ==============================================================================
# Section: test_optimization_properties.py
# ==============================================================================
"""Hypothesis property tests for machine scheduling and optimization invariants."""


from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    seed=st.integers(min_value=1, max_value=99999),
    num_jobs=st.integers(min_value=2, max_value=6),
    num_machines=st.integers(min_value=1, max_value=3),
)
def test_hypothesis_no_machine_double_booked_and_readiness_invariant(
    seed: int, num_jobs: int, num_machines: int
) -> None:
    # Generate test machines
    machines = [
        MachineResource(
            machine_id=uuid4(),
            machine_type=MachineType.HAPPY_SEEDER,
            capacity_acres_per_hour=1.2,
            hourly_cost_inr=1800.0,
            current_lat=30.8 + i * 0.01,
            current_lon=75.8 + i * 0.01,
            available_from_hour=0.0,
        )
        for i in range(num_machines)
    ]

    # Generate test jobs
    jobs = [
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=float(2.0 + j * 1.5),
            earliest_start_hour=float(j * 3.0),
            deadline_hour=float(25.0 + j * 5.0),
            center_lat=30.8 + j * 0.005,
            center_lon=75.8 + j * 0.005,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        )
        for j in range(num_jobs)
    ]

    cfg = SchedulerConfig(random_seed=seed, time_limit_seconds=1.0)
    out = solve_schedule(jobs=jobs, machines=machines, config=cfg)

    # 1. No machine double-booked (intervals on each machine do not overlap)
    by_machine: dict[object, list[object]] = {}
    for a in out.assignments:
        by_machine.setdefault(a.machine_id, []).append(a)

    for _m_id, m_assignments in by_machine.items():
        sorted_m = sorted(m_assignments, key=lambda x: x.start_hour)  # type: ignore[attr-defined]
        for idx in range(len(sorted_m) - 1):
            assert sorted_m[idx].end_hour <= sorted_m[idx + 1].start_hour + 1e-4  # type: ignore[attr-defined]

    # 2. No assignment starts before field readiness window
    job_map = {j.field_id: j for j in jobs}
    for a in out.assignments:
        req = job_map[a.field_id]
        assert a.start_hour >= req.earliest_start_hour - 1e-4
        if not a.is_on_time:
            assert a.end_hour > req.deadline_hour - 1e-4


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    seed=st.integers(min_value=1, max_value=99999),
)
def test_hypothesis_determinism_for_fixed_seed(seed: int) -> None:
    machines = [
        MachineResource(
            machine_id=uuid4(),
            machine_type=MachineType.SUPER_SEEDER,
            capacity_acres_per_hour=1.5,
            hourly_cost_inr=2000.0,
            current_lat=30.8,
            current_lon=75.8,
        )
    ]
    jobs = [
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.MARGINAL,
            area_acres=3.0,
            earliest_start_hour=0.0,
            deadline_hour=15.0,
            center_lat=30.81,
            center_lon=75.81,
            eligible_machine_types=[MachineType.SUPER_SEEDER],
        ),
        JobRequest(
            field_id=uuid4(),
            farmer_id=uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=20.0,
            center_lat=30.82,
            center_lon=75.82,
            eligible_machine_types=[MachineType.SUPER_SEEDER],
        ),
    ]

    cfg = SchedulerConfig(random_seed=seed, time_limit_seconds=1.0)
    out1 = solve_schedule(jobs=jobs, machines=machines, config=cfg)
    out2 = solve_schedule(jobs=jobs, machines=machines, config=cfg)

    assert len(out1.assignments) == len(out2.assignments)
    assert out1.objective_value == out2.objective_value
    for a1, a2 in zip(out1.assignments, out2.assignments, strict=True):
        assert a1.field_id == a2.field_id
        assert a1.machine_id == a2.machine_id
        assert a1.start_hour == a2.start_hour
        assert a1.end_hour == a2.end_hour


# ==============================================================================
# Section: test_simulation_config.py
# ==============================================================================
"""Unit tests for simulation configuration parsing and Pydantic validation."""

from pathlib import Path

import pytest

from stubbleos.simulation.config import (
    BuyerSpecConfig,
    DistrictSizeConfig,
    MachineCountsConfig,
    ScenarioConfig,
    StochasticParamsConfig,
)


def test_scenario_config_valid_defaults() -> None:
    config = ScenarioConfig(name="test-scenario")
    assert config.name == "test-scenario"
    assert config.season_length_days == 35
    assert config.is_synthetic is True
    assert len(config.config_hash()) == 16


def test_district_size_invalid_farmer_count() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 5"):
        DistrictSizeConfig(num_farmers=2)


def test_district_size_min_exceeds_max() -> None:
    with pytest.raises(ValidationError, match="fields_per_farmer_min cannot exceed fields_per_farmer_max"):
        DistrictSizeConfig(num_farmers=10, fields_per_farmer_min=5, fields_per_farmer_max=3)


def test_district_size_probabilities_must_sum_to_one() -> None:
    with pytest.raises(ValidationError, match=r"probabilities must sum to 1\.0"):
        DistrictSizeConfig(
            num_farmers=10,
            landholding_distribution={
                LandholdingClass.MARGINAL: 0.5,
                LandholdingClass.SMALL: 0.2,
                LandholdingClass.SEMI_MEDIUM: 0.1,
                LandholdingClass.MEDIUM: 0.1,
                LandholdingClass.LARGE: 0.05,  # sums to 0.95
            },
        )


def test_machine_counts_total() -> None:
    counts = MachineCountsConfig(happy_seeder=10, super_seeder=15, baler=5, rake=5)
    assert counts.total() == 35


def test_stochastic_params_validation_errors() -> None:
    with pytest.raises(
        ValidationError, match="rain_duration_hours_min cannot exceed rain_duration_hours_max"
    ):
        StochasticParamsConfig(rain_duration_hours_min=50.0, rain_duration_hours_max=20.0)

    with pytest.raises(
        ValidationError, match="deadline_window_days_min cannot exceed deadline_window_days_max"
    ):
        StochasticParamsConfig(deadline_window_days_min=25, deadline_window_days_max=10)


def test_buyer_specs_validation_errors() -> None:
    with pytest.raises(
        ValidationError, match="price_inr_per_tonne_min cannot exceed price_inr_per_tonne_max"
    ):
        BuyerSpecConfig(price_inr_per_tonne_min=3000.0, price_inr_per_tonne_max=2000.0)


@pytest.mark.parametrize(
    "scenario_name",
    [
        "baseline-district",
        "machine-scarce",
        "rain-shock",
        "low-trust",
    ],
)
def test_all_provided_scenarios_load_and_validate(scenario_name: str) -> None:
    yaml_path = Path("scenarios") / f"{scenario_name}.yaml"
    assert yaml_path.exists(), f"Scenario file {yaml_path} does not exist"
    config = ScenarioConfig.from_yaml_file(yaml_path)
    assert config.name == scenario_name
    assert config.is_synthetic is True
    assert config.district_size.num_farmers > 0
    assert config.machine_counts.total() > 0


# ==============================================================================
# Section: test_simulation_generator.py
# ==============================================================================
"""Unit tests for synthetic district generation and reproducibility."""

import json

from stubbleos.simulation.generator import generate_synthetic_district


def test_generator_determinism() -> None:
    config = ScenarioConfig(name="test-sim")
    seed = 42

    district1 = generate_synthetic_district(config, seed)
    district2 = generate_synthetic_district(config, seed)

    assert len(district1.farmers) == len(district2.farmers)
    assert len(district1.fields) == len(district2.fields)
    assert len(district1.machines) == len(district2.machines)
    assert len(district1.buyers) == len(district2.buyers)
    assert len(district1.trucks) == len(district2.trucks)

    for f1, f2 in zip(district1.farmers, district2.farmers, strict=True):
        assert f1.farmer_id == f2.farmer_id
        assert f1.total_area_acres == f2.total_area_acres
        assert f1.trust_score == f2.trust_score

    for fld1, fld2 in zip(district1.fields, district2.fields, strict=True):
        assert fld1.field_id == fld2.field_id
        assert fld1.area_acres == fld2.area_acres
        assert fld1.harvest_day == fld2.harvest_day
        assert fld1.sowing_deadline_day == fld2.sowing_deadline_day


def test_generator_labels_everything_synthetic() -> None:
    config = ScenarioConfig(name="test-sim")
    district = generate_synthetic_district(config, seed=999)

    assert district.is_synthetic is True
    assert all(f.is_synthetic for f in district.farmers)
    assert all(f.is_synthetic for f in district.fields)
    assert all(m.is_synthetic for m in district.machines)
    assert all(op.is_synthetic for op in district.operators)
    assert all(b.is_synthetic for b in district.buyers)
    assert all(t.is_synthetic for t in district.trucks)


def test_generator_calibration_file_hook(tmp_path: object) -> None:
    calib_data = {
        "lat_bounds": [31.0, 31.5],
        "lon_bounds": [76.0, 76.5],
    }
    calib_file = Path(str(tmp_path)) / "calibration.json"
    calib_file.write_text(json.dumps(calib_data), encoding="utf-8")

    config = ScenarioConfig(name="calibrated-test", calibration_file=str(calib_file))
    district = generate_synthetic_district(config, seed=123)

    for f in district.fields:
        assert 30.98 <= f.center_lat <= 31.52
        assert 75.98 <= f.center_lon <= 76.52


# ==============================================================================
# Section: test_simulation_invariants.py
# ==============================================================================
"""Invariants and conservation tests using unit assertions and Hypothesis property tests."""

import math

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from stubbleos.simulation.simulator import DistrictSimulator
from stubbleos.simulation.strategy import BaselineAStrategy, BaselineBStrategy


def test_conservation_and_physical_invariants() -> None:
    config = ScenarioConfig(name="test-invariants", season_length_days=25)
    strat = BaselineBStrategy()
    sim = DistrictSimulator(config=config, strategy=strat, seed=12345)
    state = sim.run()

    total_season_hours = config.season_length_days * 24.0

    # 1. Total acres conservation
    sum_individual_acres = sum(f.area_acres for f in state.fields)
    assert math.isclose(state.total_acres, sum_individual_acres, rel_tol=1e-5)

    # 2. Partitioning of field states (no overlaps, complete sum)
    cleared_a = sum(f.area_acres for f in state.fields if f.state == FieldState.CLEARED)
    burned_a = sum(f.area_acres for f in state.fields if f.state == FieldState.BURN_DETECTED)
    unharvested_a = sum(f.area_acres for f in state.fields if f.state == FieldState.NOT_HARVESTED)
    uncleared_a = sum(f.area_acres for f in state.fields if f.state == FieldState.HARVESTED_RESIDUE_PRESENT)

    partition_sum = cleared_a + burned_a + unharvested_a + uncleared_a
    assert math.isclose(partition_sum, state.total_acres, rel_tol=1e-5)

    # 3. No field is both cleared and burned
    for field in state.fields:
        assert not (field.is_cleared and field.is_burned), (
            f"Field {field.field_id} is both cleared and burned!"
        )
        assert field.area_acres > 0.0
        assert field.residue_tonnes_est > 0.0

    # 4. Conservation of machine operating hours
    for m in state.machines:
        total_m_hours = m.operating_hours + m.transit_hours + m.breakdown_hours + m.idle_hours
        assert math.isclose(total_m_hours, total_season_hours, abs_tol=0.1)
        assert m.operating_hours >= 0.0
        assert m.idle_hours >= 0.0
        assert m.breakdown_hours >= 0.0
        assert m.transit_hours >= 0.0


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    seed=st.integers(min_value=1, max_value=99999),
    num_farmers=st.integers(min_value=10, max_value=30),
    season_days=st.integers(min_value=14, max_value=30),
)
def test_hypothesis_simulation_invariants_hold(seed: int, num_farmers: int, season_days: int) -> None:
    config = ScenarioConfig(
        name="prop-test",
        season_length_days=season_days,
        district_size=DistrictSizeConfig(num_farmers=num_farmers),
    )
    # Test property on Baseline A
    strat_a = BaselineAStrategy()
    sim_a = DistrictSimulator(config=config, strategy=strat_a, seed=seed)
    state_a = sim_a.run()

    # Invariants for run
    assert state_a.total_acres > 0.0
    for f in state_a.fields:
        assert f.area_acres > 0.0
        assert not (f.is_cleared and f.is_burned)
        if f.is_cleared:
            assert f.cleared_at_day is not None
            assert f.cleared_at_day >= f.harvest_day
        if f.is_burned:
            assert f.burned_at_day is not None
            assert f.burned_at_day >= f.harvest_day

    # Straw deliveries never exceed total crop residue
    assert state_a.delivered_straw_tonnes <= state_a.total_straw_tonnes + 1e-4

    # Test property on Baseline B
    strat_b = BaselineBStrategy()
    sim_b = DistrictSimulator(config=config, strategy=strat_b, seed=seed)
    state_b = sim_b.run()

    assert state_b.total_acres > 0.0
    for f in state_b.fields:
        assert not (f.is_cleared and f.is_burned)


# ==============================================================================
# Section: test_simulation_determinism.py
# ==============================================================================
"""Unit tests verifying strict byte-identical simulation determinism."""

from stubbleos.simulation.metrics import compute_run_metrics


def test_baseline_a_byte_identical_determinism() -> None:
    config = ScenarioConfig(name="test-determinism")
    seed = 4242

    # Run 1
    strat1 = BaselineAStrategy()
    sim1 = DistrictSimulator(config=config, strategy=strat1, seed=seed)
    state1 = sim1.run()
    metrics1 = compute_run_metrics(
        state=state1,
        strategy=strat1,
        scenario_name=config.name,
        seed=seed,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    # Run 2
    strat2 = BaselineAStrategy()
    sim2 = DistrictSimulator(config=config, strategy=strat2, seed=seed)
    state2 = sim2.run()
    metrics2 = compute_run_metrics(
        state=state2,
        strategy=strat2,
        scenario_name=config.name,
        seed=seed,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    # Exclude git_commit timestamp/hash variance if any, though it's identical
    json1 = metrics1.model_dump_json()
    json2 = metrics2.model_dump_json()

    assert json1 == json2, "Runs with identical config and seed must produce byte-identical metrics output"


def test_baseline_b_byte_identical_determinism() -> None:
    config = ScenarioConfig(name="test-determinism")
    seed = 8888

    # Run 1
    strat1 = BaselineBStrategy()
    sim1 = DistrictSimulator(config=config, strategy=strat1, seed=seed)
    state1 = sim1.run()
    metrics1 = compute_run_metrics(
        state=state1,
        strategy=strat1,
        scenario_name=config.name,
        seed=seed,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    # Run 2
    strat2 = BaselineBStrategy()
    sim2 = DistrictSimulator(config=config, strategy=strat2, seed=seed)
    state2 = sim2.run()
    metrics2 = compute_run_metrics(
        state=state2,
        strategy=strat2,
        scenario_name=config.name,
        seed=seed,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    assert metrics1.model_dump_json() == metrics2.model_dump_json()


def test_different_seeds_produce_different_metrics() -> None:
    config = ScenarioConfig(name="test-determinism")

    strat1 = BaselineBStrategy()
    sim1 = DistrictSimulator(config=config, strategy=strat1, seed=1111)
    state1 = sim1.run()
    metrics1 = compute_run_metrics(
        state=state1,
        strategy=strat1,
        scenario_name=config.name,
        seed=1111,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    strat2 = BaselineBStrategy()
    sim2 = DistrictSimulator(config=config, strategy=strat2, seed=2222)
    state2 = sim2.run()
    metrics2 = compute_run_metrics(
        state=state2,
        strategy=strat2,
        scenario_name=config.name,
        seed=2222,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    assert metrics1.model_dump_json() != metrics2.model_dump_json()


# ==============================================================================
# Section: test_simulation_metrics.py
# ==============================================================================
"""Unit tests for simulation metrics computation and aggregation with hand-computed tiny cases."""


from stubbleos.core.types import (
    MachineStatus,
)
from stubbleos.simulation.metrics import (
    compute_confidence_intervals,
)
from stubbleos.simulation.model import (
    DistrictState,
    SimulatedBuyer,
    SimulatedFarmer,
    SimulatedField,
    SimulatedMachine,
    SimulatedTruck,
)


def test_hand_computed_tiny_district_metrics() -> None:
    # 4 farmers: 2 smallholders (marginal, small), 2 largeholders (medium, large)
    farmer_a = SimulatedFarmer(
        farmer_id=uuid4(),
        pseudonym="farmer_a",
        landholding_class=LandholdingClass.MARGINAL,
        total_area_acres=2.0,
        trust_score=0.8,
        income_band="low",
        preferred_language=Language.PUNJABI,
        field_ids=[],
        net_income_inr=5000.0,
    )
    farmer_b = SimulatedFarmer(
        farmer_id=uuid4(),
        pseudonym="farmer_b",
        landholding_class=LandholdingClass.SMALL,
        total_area_acres=3.0,
        trust_score=0.6,
        income_band="low",
        preferred_language=Language.PUNJABI,
        field_ids=[],
        net_income_inr=3000.0,
    )
    farmer_c = SimulatedFarmer(
        farmer_id=uuid4(),
        pseudonym="farmer_c",
        landholding_class=LandholdingClass.MEDIUM,
        total_area_acres=5.0,
        trust_score=0.5,
        income_band="medium",
        preferred_language=Language.HINDI,
        field_ids=[],
        net_income_inr=-7500.0,
    )
    farmer_d = SimulatedFarmer(
        farmer_id=uuid4(),
        pseudonym="farmer_d",
        landholding_class=LandholdingClass.LARGE,
        total_area_acres=10.0,
        trust_score=0.4,
        income_band="high",
        preferred_language=Language.PUNJABI,
        field_ids=[],
        net_income_inr=0.0,
    )

    # 4 fields matching the hand-computed scenario
    field_1 = SimulatedField(
        field_id=uuid4(),
        farmer_id=farmer_a.farmer_id,
        area_acres=2.0,
        residue_tonnes_est=5.0,
        harvest_day=5.0,
        sowing_deadline_day=15.0,
        state=FieldState.CLEARED,
        cleared_at_day=12.0,  # Cleared BEFORE deadline
        center_lat=30.8,
        center_lon=75.8,
        polygon_coords=[],
    )
    field_2 = SimulatedField(
        field_id=uuid4(),
        farmer_id=farmer_b.farmer_id,
        area_acres=3.0,
        residue_tonnes_est=7.5,
        harvest_day=5.0,
        sowing_deadline_day=16.0,
        state=FieldState.CLEARED,
        cleared_at_day=18.0,  # Cleared AFTER deadline
        center_lat=30.81,
        center_lon=75.81,
        polygon_coords=[],
    )
    field_3 = SimulatedField(
        field_id=uuid4(),
        farmer_id=farmer_c.farmer_id,
        area_acres=5.0,
        residue_tonnes_est=12.5,
        harvest_day=6.0,
        sowing_deadline_day=14.0,
        state=FieldState.BURN_DETECTED,
        burned_at_day=14.0,  # Burned!
        center_lat=30.82,
        center_lon=75.82,
        polygon_coords=[],
    )
    field_4 = SimulatedField(
        field_id=uuid4(),
        farmer_id=farmer_d.farmer_id,
        area_acres=10.0,
        residue_tonnes_est=25.0,
        harvest_day=7.0,
        sowing_deadline_day=20.0,
        state=FieldState.HARVESTED_RESIDUE_PRESENT,
        center_lat=30.83,
        center_lon=75.83,
        polygon_coords=[],
    )

    # 2 machines
    machine_1 = SimulatedMachine(
        machine_id=uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.0,
        hourly_cost_inr=1800.0,
        status=MachineStatus.AVAILABLE,
        current_lat=30.8,
        current_lon=75.8,
        home_lat=30.8,
        home_lon=75.8,
        operating_hours=20.0,
        idle_hours=80.0,
    )
    machine_2 = SimulatedMachine(
        machine_id=uuid4(),
        machine_type=MachineType.BALER,
        capacity_acres_per_hour=2.0,
        hourly_cost_inr=2400.0,
        status=MachineStatus.AVAILABLE,
        current_lat=30.8,
        current_lon=75.8,
        home_lat=30.8,
        home_lon=75.8,
        operating_hours=30.0,
        idle_hours=70.0,
    )

    # 1 buyer and 1 truck
    buyer = SimulatedBuyer(
        buyer_id=uuid4(),
        org_name="Buyer_Bio_syn",
        buyer_type=BuyerType.BIOMASS_PLANT,
        lat=30.9,
        lon=75.9,
        tonnes_required=100.0,
        tonnes_filled=10.0,
        price_inr_per_tonne=2000.0,
        max_moisture_pct=16.0,
    )
    truck = SimulatedTruck(
        truck_id=uuid4(),
        capacity_tonnes=10.0,
        cost_per_km_inr=45.0,
        total_km_travelled=100.0,
        total_tonnes_hauled=10.0,
    )

    state = DistrictState(
        district_name="tiny-test",
        farmers=[farmer_a, farmer_b, farmer_c, farmer_d],
        fields=[field_1, field_2, field_3, field_4],
        machines=[machine_1, machine_2],
        operators=[],
        buyers=[buyer],
        trucks=[truck],
    )

    strat = BaselineAStrategy()
    metrics = compute_run_metrics(
        state=state,
        strategy=strat,
        scenario_name="tiny-test",
        seed=1,
        config_hash="abc12345",
        season_length_days=10,  # 10 days * 24h = 240 hours per machine -> 480 total machine capacity hours
        baseline_a_avg_income=100.0,
    )

    # 1. % fields cleared before deadline: 1 out of 4 = 25.0%
    assert metrics.pct_fields_cleared_before_deadline == 25.0

    # 2. Total acres = 2 + 3 + 5 + 10 = 20.0
    assert metrics.total_acres == 20.0

    # 3. Burn events per 1000 acres: 1 event / 20.0 acres * 1000 = 50.0
    assert metrics.total_burn_events == 1
    assert metrics.burn_events_per_1000_acres == 50.0

    # 4. Machine utilization: (20 + 30) / (2 * 240) = 50 / 480 = 10.42%
    assert metrics.machine_utilization_pct == 10.42

    # 5. Average machine idle hours: (80 + 70) / 2 = 75.0
    assert metrics.average_machine_idle_hours == 75.0

    # 6. Straw delivered & fill rate: 10 tonnes delivered / 100 required = 10.0%
    assert metrics.straw_tonnage_delivered == 10.0
    assert metrics.buyer_order_fill_rate_pct == 10.0

    # 7. Average farmer income: (5000 + 3000 - 7500 + 0) / 4 = 500 / 4 = 125.0 INR
    assert metrics.avg_farmer_net_income_inr == 125.0
    assert metrics.farmer_net_income_delta_vs_baseline_a == 25.0  # 125.0 - 100.0

    # 8. Logistics cost and CO2 per ton: 100 km * 45 INR/km / 10 tons = 450.0 INR/ton
    assert metrics.logistics_cost_per_ton_inr == 450.0
    # CO2: 100 km * 1.42 kg/km / 10 tons = 14.2 kg CO2/ton
    assert metrics.logistics_co2_kg_per_ton == 14.2

    # 9. Fairness gap:
    # Smallholders: farmer_a (cleared before deadline), farmer_b (cleared late) -> 1/2 = 50.0%
    # Largeholders: farmer_c (burned), farmer_d (uncleared) -> 0/2 = 0.0%
    # Gap = Large (0.0) - Small (50.0) = -50.0%
    assert metrics.smallholder_clearance_pct == 50.0
    assert metrics.largeholder_clearance_pct == 0.0
    assert metrics.fairness_gap_pct == -50.0


def test_confidence_intervals_constant_and_normal() -> None:
    # Constant array
    ci_t, ci_boot = compute_confidence_intervals([15.0, 15.0, 15.0, 15.0])
    assert ci_t == (15.0, 15.0)
    assert ci_boot == (15.0, 15.0)

    # Varying array: mean = 30.0
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    ci_t, ci_boot = compute_confidence_intervals(vals)
    assert ci_t[0] < 30.0 < ci_t[1]
    assert ci_boot[0] < 30.0 < ci_boot[1]


# ==============================================================================
# Section: test_simulation_run.py
# ==============================================================================
"""Unit tests for simulation runner CLI and experiment execution."""


import pytest

from stubbleos.simulation.run import (
    instantiate_strategy,
    resolve_scenario_path,
    run_experiment,
)


def test_resolve_scenario_path() -> None:
    path = resolve_scenario_path("baseline-district")
    assert path.exists()
    assert path.name == "baseline-district.yaml"

    with pytest.raises(FileNotFoundError, match="Scenario configuration not found"):
        resolve_scenario_path("non-existent-scenario")


def test_instantiate_strategy() -> None:
    strat_a = instantiate_strategy("baseline_a")
    assert strat_a.name == "baseline_a"

    strat_b = instantiate_strategy("baseline-b")
    assert strat_b.name == "baseline_b"

    with pytest.raises(ValueError, match="Unknown strategy"):
        instantiate_strategy("unknown_strategy")


def test_run_experiment_execution_and_file_export(tmp_path: Path) -> None:
    out_dir = tmp_path / "results"
    report, runs = run_experiment(
        scenario_path="baseline-district",
        strategy_name="baseline_b",
        num_seeds=2,
        seed_start=2000,
        out_dir=out_dir,
    )

    assert report.scenario_name == "baseline-district"
    assert report.strategy_name == "baseline_b"
    assert len(runs) == 2
    assert report.num_seeds == 2
    assert report.is_synthetic is True

    result_dir = out_dir / "baseline-district_baseline_b"
    assert result_dir.exists()

    summary_file = result_dir / "summary.json"
    assert summary_file.exists()
    with open(summary_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["scenario_name"] == "baseline-district"
    assert "metrics" in data

    csv_file = result_dir / "runs.csv"
    assert csv_file.exists()
    lines = csv_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3  # Header + 2 rows


# ==============================================================================
# Section: test_simulation_strategies.py
# ==============================================================================
"""Unit tests for coordination strategies: Baseline A, Baseline B, and StubbleOS stubs."""


from stubbleos.simulation.strategy import (
    StubbleOSCentralizedStrategy,
    StubbleOSDecentralizedStrategy,
)


def test_baseline_a_strategy_behavior() -> None:
    config = ScenarioConfig(name="test")
    state = generate_synthetic_district(config, seed=42)
    rng = np.random.default_rng(42)

    strategy = BaselineAStrategy(search_radius_km=15.0, p_seek_machine=1.0)
    strategy.initialize(state, rng)

    field = state.fields[0]
    field.state = FieldState.HARVESTED_RESIDUE_PRESENT

    # Since all machines are initially AVAILABLE, searching should find a machine
    machine = strategy.on_field_harvested(field, current_day=5.0)
    assert machine is not None
    assert strategy.has_confirmed_booking(field.field_id) is True

    # on_machine_available does nothing in Baseline A (uncoordinated)
    assert strategy.on_machine_available(machine, current_day=6.0) is None


def test_baseline_b_fcfs_queue_behavior() -> None:
    config = ScenarioConfig(name="test")
    state = generate_synthetic_district(config, seed=42)
    rng = np.random.default_rng(42)

    strategy = BaselineBStrategy()
    strategy.initialize(state, rng)

    # Harvest two fields
    field1 = state.fields[0]
    field2 = state.fields[1]
    field1.state = FieldState.HARVESTED_RESIDUE_PRESENT
    field2.state = FieldState.HARVESTED_RESIDUE_PRESENT

    # First field gets immediate idle machine
    m1 = strategy.on_field_harvested(field1, current_day=2.0)
    assert m1 is not None

    # Mark all machines as busy to test queueing
    for m in state.machines:
        m.status = MachineStatus.IN_USE

    m2 = strategy.on_field_harvested(field2, current_day=2.1)
    assert m2 is None
    assert strategy.has_confirmed_booking(field2.field_id) is True
    assert len(strategy.queue) == 1

    # Now free up a machine and check FCFS dispatch
    test_machine = state.machines[0]
    test_machine.status = MachineStatus.AVAILABLE

    assigned_field = strategy.on_machine_available(test_machine, current_day=2.5)
    assert assigned_field is not None
    assert assigned_field.field_id == field2.field_id
    assert len(strategy.queue) == 0


def test_stubbleos_strategies_behavior() -> None:
    config = ScenarioConfig(name="test")
    state = generate_synthetic_district(config, seed=42)
    rng = np.random.default_rng(42)

    field = state.fields[0]
    field.state = FieldState.HARVESTED_RESIDUE_PRESENT

    # Centralized Strategy
    centralized = StubbleOSCentralizedStrategy(time_limit_seconds=0.5)
    centralized.initialize(state, rng)
    assigned_m = centralized.on_field_harvested(field, current_day=1.0)
    assert centralized.has_confirmed_booking(field.field_id) is True
    assert assigned_m is not None

    # Decentralized Strategy
    decentralized = StubbleOSDecentralizedStrategy()
    decentralized.initialize(state, rng)
    m_award = decentralized.on_field_harvested(field, current_day=1.0)
    assert decentralized.has_confirmed_booking(field.field_id) is True
    assert m_award is not None


# ==============================================================================
# Section: test_evaluation_matrix.py
# ==============================================================================
"""Unit tests for evaluation matrix and benchmarks."""


from stubbleos.evals.benchmarks import (
    benchmark_api_endpoints,
    benchmark_cpsat_scheduler,
    benchmark_eventbus_throughput,
    benchmark_pii_redaction,
    run_all_benchmarks,
)
from stubbleos.evals.matrix import (
    execute_evaluation_matrix,
    generate_markdown_summary,
    update_results_files,
)


def test_benchmark_cpsat_scheduler():
    results = benchmark_cpsat_scheduler(sizes=[5, 10])
    assert len(results) == 2
    assert results[0]["num_jobs"] == 5
    assert results[0]["solve_latency_ms"] >= 0.0
    assert results[0]["solver_status"] in ("OPTIMAL", "FEASIBLE")


def test_benchmark_eventbus_throughput():
    res = benchmark_eventbus_throughput(event_count=50)
    assert res["events_dispatched"] == 50
    assert res["events_received"] == 50
    assert res["throughput_events_per_sec"] > 0.0


def test_benchmark_pii_redaction():
    res = benchmark_pii_redaction(iterations=50)
    assert res["redaction_calls"] == 50
    assert res["throughput_ops_per_sec"] > 0.0


def test_benchmark_api_endpoints():
    res = benchmark_api_endpoints()
    assert "GET /healthz" in res
    assert "GET /readyz" in res
    assert "GET /api/v1/fields" in res
    assert all(lat >= 0.0 for lat in res.values())


def test_run_all_benchmarks():
    data = run_all_benchmarks()
    assert "scheduler_latency" in data
    assert "event_bus_throughput" in data
    assert "pii_redaction_throughput" in data
    assert "api_endpoint_latency_ms" in data


def test_evaluation_matrix_execution(tmp_path: Path):
    # Execute 1 scenario, 2 strategies, 1 seed for fast unit test
    matrix = execute_evaluation_matrix(
        scenarios=["baseline-district"],
        strategies=["baseline_a", "stubbleos_centralized"],
        num_seeds=1,
        seed_start=2000,
        out_dir=tmp_path / "results",
    )

    assert len(matrix.reports) == 2
    assert ("baseline-district", "baseline_a") in matrix.reports
    assert ("baseline-district", "stubbleos_centralized") in matrix.reports

    md = generate_markdown_summary(matrix)
    assert "Scenario: `baseline-district`" in md
    assert "`baseline_a`" in md
    assert "`stubbleos_centralized`" in md

    # Test update_results_files
    update_results_files(matrix, root_dir=tmp_path)
    assert (tmp_path / "results" / "evaluation_matrix.json").exists()
    assert (tmp_path / "results" / "evaluation_summary.md").exists()
    assert (tmp_path / "docs" / "RESULTS.md").exists()


# ==============================================================================
# Section: test_chaos_resilience.py
# ==============================================================================
"""Unit tests for chaos engineering and resilience assertions."""


import pytest

from stubbleos.evals.chaos import (
    run_all_chaos_tests,
    run_audit_tampering_chaos,
    run_double_booking_conflict_chaos,
    run_machine_breakdown_chaos,
    run_quiet_hours_chaos,
    run_spatial_privacy_export_chaos,
)
from stubbleos.evals.privacy import (
    ExportFieldRecord,
    SpatialExportPolicyViolation,
    sanitize_for_external_export,
    validate_export_payload,
)


@pytest.fixture
def test_engine():
    return create_engine(
        "sqlite:///:memory:",
        execution_options={"schema_translate_map": {"core": None, "pii": None}},
    )


def test_machine_breakdown_chaos():
    res = run_machine_breakdown_chaos()
    assert res.passed is True
    assert "machine_breakdown_50pct" in res.name


def test_quiet_hours_chaos():
    res = run_quiet_hours_chaos()
    assert res.passed is True
    assert "quiet_hours_breach_protection" in res.name


def test_audit_tampering_chaos(test_engine):
    res = run_audit_tampering_chaos(test_engine)
    assert res.passed is True
    assert "audit_tamper_detection" in res.name


def test_double_booking_conflict_chaos():
    res = run_double_booking_conflict_chaos()
    assert res.passed is True
    assert "conflict_resolution_and_fairness" in res.name


def test_spatial_privacy_export_chaos():
    res = run_spatial_privacy_export_chaos()
    assert res.passed is True
    assert "spatial_privacy_export_policy" in res.name


def test_run_all_chaos_tests(test_engine):
    results = run_all_chaos_tests(test_engine)
    assert len(results) == 5
    for r in results:
        assert r.passed is True, f"Chaos test {r.name} failed: {r.details}"


def test_spatial_export_policy_violations():
    # Sensitive boundary_wkt key
    with pytest.raises(SpatialExportPolicyViolation):
        validate_export_payload({"district": "ludhiana", "boundary_wkt": "POLYGON(...)"})

    # Sensitive farmer phone
    with pytest.raises(SpatialExportPolicyViolation):
        validate_export_payload({"district": "ludhiana", "records": [{"phone_number": "+919876543210"}]})


def test_sanitize_for_external_export_k_anonymity():
    # 2 fields in village A (below k=3), 4 fields in village B (>= k=3)
    records = [
        ExportFieldRecord(
            field_id=uuid4(),
            farmer_id=uuid4(),
            village_name="small_hamlet",
            district_name="ludhiana",
            area_acres=3.0,
            center_lat=30.80,
            center_lon=75.80,
            harvest_day=1.0,
            sowing_deadline_day=15.0,
            cleared_at_day=10.0,
            burned=False,
        )
        for _ in range(2)
    ] + [
        ExportFieldRecord(
            field_id=uuid4(),
            farmer_id=uuid4(),
            village_name="large_village",
            district_name="ludhiana",
            area_acres=5.0,
            center_lat=30.85,
            center_lon=75.85,
            harvest_day=1.0,
            sowing_deadline_day=15.0,
            cleared_at_day=12.0,
            burned=False,
        )
        for _ in range(4)
    ]

    summaries = sanitize_for_external_export(records, min_k_anonymity=3)
    assert len(summaries) == 2

    # Check village-level summary
    village_b = next(s for s in summaries if s.village_name == "large_village")
    assert village_b.total_fields == 4
    assert village_b.spatial_precision == "village_centroid"

    # Check district fallback residual
    residual = next(s for s in summaries if "residual" in s.village_name)
    assert residual.total_fields == 2
    assert residual.spatial_precision == "district_centroid_fallback"


# ==============================================================================
# Section: test_go_live_gate.py
# ==============================================================================
"""Go-Live Master Gate Automated Verification Test Suite.

Directly asserts that every criterion of the 02_MASTER_DEPLOYMENT_GUIDE.md §19
and 03_AI_SECURITY_PLAYBOOK.md §9 Go-Live Checklist is satisfied with empirical proof.
"""


import yaml

from stubbleos.data.models import AuditLog, Consent


def test_gate_01_core_architecture_and_readme_exist() -> None:
    assert Path("README.md").exists()
    assert Path("src/stubbleos").exists()
    assert Path("evals/datasets").exists()


def test_gate_02_operational_datasets_and_configs_exist() -> None:
    assert Path("evals/datasets/smoke.jsonl").exists()
    assert Path("evals/datasets/golden_core.jsonl").exists()
    assert Path("evals/datasets/adversarial_redteam.jsonl").exists()


def test_gate_03_eval_corpora_and_metrics_registry() -> None:
    # Datasets
    for ds_path, min_sz in [
        ("evals/datasets/smoke.jsonl", 30),
        ("evals/datasets/golden_core.jsonl", 100),
        ("evals/datasets/adversarial_redteam.jsonl", 50),
    ]:
        p = Path(ds_path)
        assert p.exists()
        lines = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) >= min_sz

    # Metrics registry
    m_path = Path("evals/metrics.yaml")
    assert m_path.exists()
    cfg = yaml.safe_load(m_path.read_text(encoding="utf-8"))
    assert "metrics" in cfg
    assert "segments" in cfg
    assert cfg["metrics"]["policy_guard_compliance"]["min_abs"] == 1.00


def test_gate_04_policy_guard_quiet_hours_and_consent() -> None:
    # Quiet hours: 08:00 to 19:00 IST permitted
    # 07:30 IST (02:00 UTC) -> must be blocked
    dt_morning_blocked = datetime(2026, 10, 20, 2, 0, tzinfo=UTC)
    ok, detail = check_contact_hours(dt_morning_blocked, 8, 19)
    assert not ok
    assert "outside allowed window" in (detail or "")

    # 12:00 IST (06:30 UTC) -> must be allowed
    dt_noon_allowed = datetime(2026, 10, 20, 6, 30, tzinfo=UTC)
    ok, detail = check_contact_hours(dt_noon_allowed, 8, 19)
    assert ok
    assert detail is None

    # 21:00 IST (15:30 UTC) -> must be blocked
    dt_night_blocked = datetime(2026, 10, 20, 15, 30, tzinfo=UTC)
    ok, detail = check_contact_hours(dt_night_blocked, 8, 19)
    assert not ok

    # Consent ledger
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"core": None, "pii": None})
    Base.metadata.create_all(engine, tables=[Consent.__table__])
    sm = sessionmaker(engine, expire_on_commit=False)
    with sm() as session:
        repo = ConsentRepository(session)
        fid = uuid4()
        now = datetime(2026, 10, 20, 6, 30, tzinfo=UTC)
        assert not repo.has_valid_consent(fid, ConsentPurpose.OUTREACH, Channel.WHATSAPP, now)

        repo.record(
            farmer_id=fid,
            purpose=ConsentPurpose.OUTREACH,
            channel=Channel.WHATSAPP,
            granted=True,
            language=Language.PUNJABI,
            at=now - timedelta(hours=1),
            recorded_by="onboarding",
        )
        assert repo.has_valid_consent(fid, ConsentPurpose.OUTREACH, Channel.WHATSAPP, now)


def test_gate_05_cryptographic_audit_trail_and_tamper_detection() -> None:
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"core": None, "pii": None})
    Base.metadata.create_all(engine, tables=[AuditLog.__table__])
    sm = sessionmaker(engine, expire_on_commit=False)
    with sm() as session:
        repo = AuditLogRepository(session)
        t0 = datetime(2026, 10, 20, 6, 0, tzinfo=UTC)

        for i in range(5):
            repo.append(
                ts=t0 + timedelta(minutes=i),
                actor="test_agent",
                action="booking.created",
                entity_type="booking",
                entity_id=str(i),
                details={"step": i},
            )
        session.commit()

        # Valid chain
        verification = repo.verify_chain()
        assert verification.ok is True
        assert verification.entries_checked == 5

        # Tampering detection
        from sqlalchemy import text

        session.execute(text("UPDATE audit_log SET actor = 'adversary' WHERE id = 3"))
        session.commit()

        tampered = repo.verify_chain()
        assert tampered.ok is False
        assert tampered.first_bad_id == 3


def test_gate_06_cpsat_scheduler_and_smallholder_fairness() -> None:
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.SUPER_SEEDER,
        capacity_acres_per_hour=1.0,
        hourly_cost_inr=1500.0,
        current_lat=30.8,
        current_lon=75.8,
        available_from_hour=0.0,
    )

    marginal = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.MARGINAL,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=3.5,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )
    large = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.LARGE,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=3.5,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )

    out = solve_schedule(
        jobs=[marginal, large],
        machines=[machine],
        config=SchedulerConfig(time_limit_seconds=0.5, random_seed=42),
    )
    assert out.solver_status in ("OPTIMAL", "FEASIBLE")
    on_time = [a for a in out.assignments if a.is_on_time]
    assert len(on_time) == 1
    # Marginal farmer must win allocation due to 1.4x weighting multiplier
    assert on_time[0].field_id == marginal.field_id


def test_gate_07_contract_net_auction_breakdown_recovery() -> None:
    coord = ContractNetCoordinator(seed=42)
    task = TaskAnnouncement(
        task_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SMALL,
        area_acres=5.0,
        center_lat=30.85,
        center_lon=75.85,
        earliest_start_hour=0.0,
        deadline_hour=24.0,
        eligible_machine_types=[MachineType.HAPPY_SEEDER],
    )
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.5,
        hourly_cost_inr=1800.0,
        current_lat=30.86,
        current_lon=75.86,
        available_from_hour=0.0,
    )
    res = coord.run_auction_round(tasks=[task], machines=[machine], current_hour=0.0)
    assert res.bids_count == 1
    assert len(res.awards) == 1
    assert res.awards[0].machine_id == machine.machine_id


def test_gate_08_simulation_reproducibility() -> None:
    cfg = ScenarioConfig(name="gate-test-scenario")
    seed = 9999

    sim1 = DistrictSimulator(config=cfg, strategy=BaselineAStrategy(), seed=seed)
    s1 = sim1.run()
    m1 = compute_run_metrics(
        state=s1,
        strategy=sim1.strategy,
        scenario_name=cfg.name,
        seed=seed,
        config_hash=cfg.config_hash(),
        season_length_days=cfg.season_length_days,
    )

    sim2 = DistrictSimulator(config=cfg, strategy=BaselineAStrategy(), seed=seed)
    s2 = sim2.run()
    m2 = compute_run_metrics(
        state=s2,
        strategy=sim2.strategy,
        scenario_name=cfg.name,
        seed=seed,
        config_hash=cfg.config_hash(),
        season_length_days=cfg.season_length_days,
    )

    assert m1.model_dump_json() == m2.model_dump_json()


# ==============================================================================
# Section: test_migrations.py
# ==============================================================================
"""Needs a live PostGIS database at STUBBLEOS_DATABASE_URL. Run: make up && make test-int"""

import os
import subprocess
import sys
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, OperationalError

from stubbleos.data.models import CORE, CORE_TABLES_REQUIRED, PII


def alembic(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "alembic", *args], check=True, env=os.environ.copy())  # noqa: S603


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    url = Settings(_env_file=None).database_url  # type: ignore[call-arg]
    eng = create_engine(url)
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("no Postgres reachable at STUBBLEOS_DATABASE_URL")
    yield eng
    eng.dispose()


@pytest.mark.integration
def test_upgrade_creates_schema_and_audit_log_is_immutable(engine: Engine) -> None:
    alembic("downgrade", "base")
    alembic("upgrade", "head")
    with engine.begin() as c:
        core = {
            r[0]
            for r in c.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"), {"s": CORE}
            )
        }
        pii = {
            r[0]
            for r in c.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"), {"s": PII}
            )
        }
        assert core >= CORE_TABLES_REQUIRED
        assert pii == {"farmer_identities", "operator_identities", "buyer_contacts", "conversation_messages"}
        c.execute(
            text(
                "INSERT INTO core.audit_log (ts, actor, action, entity_type, details, prev_hash, entry_hash) "
                "VALUES (now(), 'a', 'x', 't', '{}', :p, :h)"
            ),
            {"p": "0" * 64, "h": "1" * 64},
        )
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
        c.execute(text("UPDATE core.audit_log SET actor = 'mallory'"))
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
        c.execute(text("DELETE FROM core.audit_log"))
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
        c.execute(text("TRUNCATE core.audit_log"))


@pytest.mark.integration
def test_impact_label_constraint_rejects_unlabeled_rows(engine: Engine) -> None:
    alembic("upgrade", "head")
    with pytest.raises(DBAPIError, match="label_disclaimer"), engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO core.impact_records (id, field_id, season, status, label, burn_avoided, area_acres, "
                "method_note, evidence_ids, record_sha256, is_synthetic) VALUES (gen_random_uuid(), gen_random_uuid(), 's', "
                "'indicative', 'verified carbon credit', true, 1, '', '[]', 'x', true)"
            )
        )


@pytest.mark.integration
def test_downgrade_is_clean(engine: Engine) -> None:
    alembic("downgrade", "base")
    with engine.begin() as c:
        left = c.execute(
            text("SELECT count(*) FROM information_schema.schemata WHERE schema_name IN ('core','pii')")
        ).scalar_one()
    assert left == 0
    alembic("upgrade", "head")


# ==============================================================================
# Section: test_redis_bus.py
# ==============================================================================
"""Needs Redis at STUBBLEOS_REDIS_URL. Run: make up && make test-int"""

import asyncio

import pytest

from stubbleos.core.events import FieldStateChanged, RedisEventBus


@pytest.mark.integration
async def test_publish_is_received_by_listener() -> None:
    url = Settings(_env_file=None).redis_url  # type: ignore[call-arg]
    bus = RedisEventBus(url)
    try:
        await bus._redis.ping()
    except Exception:
        pytest.skip("no Redis reachable")
    got: list[Event] = []

    async def handler(e: Event) -> None:
        got.append(e)

    bus.subscribe("field.*", handler)
    await bus.start()
    try:
        await asyncio.sleep(0.1)
        p = FieldStateChanged(field_id=uuid.uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.5)
        sent = await bus.emit(p, source="t")
        for _ in range(50):
            if got:
                break
            await asyncio.sleep(0.05)
        assert got
        assert got[0].event_id == sent.event_id
    finally:
        await bus.stop()
