"""Unit tests for Policy & Safety Guard agent."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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
from stubbleos.core.clock import IST
from stubbleos.core.types import Channel, ConsentPurpose, Language
from stubbleos.data.models import Base, Consent
from stubbleos.data.repositories import ConsentRepository

TABLES = [Consent.__table__]


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"core": None, "pii": None})
    Base.metadata.create_all(engine, tables=TABLES)
    sm = sessionmaker(engine, expire_on_commit=False)
    with sm() as s:
        yield s
    engine.dispose()


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
