"""Contract tests for typed agent event payloads."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from stubbleos.core.events import (
    ApprovalRequested,
    ApprovalResolved,
    BurnDetected,
    Event,
    MachineBreakdown,
    PlanCreated,
    PolicyViolationDetected,
    ReplanTriggered,
)
from stubbleos.core.types import ApprovalStatus, ReplanReason


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
