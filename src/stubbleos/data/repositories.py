"""Repositories for the Phase-1 aggregates: agent events, consent ledger, hash-chained audit log."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from stubbleos.core.clock import as_utc
from stubbleos.core.events import Event
from stubbleos.core.types import ApprovalStatus, Channel, ConsentPurpose, Language, PlanStatus
from stubbleos.data.models import AgentEvent, Approval, AuditLog, Consent, Plan

GENESIS_HASH = "0" * 64
_AUDIT_LOCK_KEY = 727_001


class AgentEventRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, event: Event) -> bool:
        """Idempotent insert. Returns False if the event id already exists."""
        if self._s.get(AgentEvent, event.event_id) is not None:
            return False
        self._s.add(
            AgentEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                source=event.source,
                ts=event.ts,
                correlation_id=event.correlation_id,
                district=event.district,
                payload=event.payload,
            )
        )
        self._s.flush()
        return True

    def by_correlation(self, correlation_id: uuid.UUID) -> list[Event]:
        rows = self._s.scalars(
            select(AgentEvent).where(AgentEvent.correlation_id == correlation_id).order_by(AgentEvent.ts)
        ).all()
        return [
            Event(
                event_id=r.event_id,
                event_type=r.event_type,
                source=r.source,
                ts=as_utc(r.ts),
                correlation_id=r.correlation_id,
                district=r.district,
                payload=r.payload,
            )
            for r in rows
        ]


class ConsentRepository:
    """Consent ledger. ``has_valid_consent`` is what the Policy Guard calls before any outreach."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def record(
        self,
        *,
        farmer_id: uuid.UUID,
        purpose: ConsentPurpose,
        channel: Channel,
        granted: bool,
        language: Language,
        at: datetime,
        recorded_by: str,
        evidence_ref: str | None = None,
        expires_at: datetime | None = None,
    ) -> Consent:
        row = Consent(
            farmer_id=farmer_id,
            purpose=purpose,
            channel=channel,
            granted=granted,
            language=language,
            recorded_at=as_utc(at),
            expires_at=as_utc(expires_at) if expires_at else None,
            evidence_ref=evidence_ref,
            recorded_by=recorded_by,
        )
        self._s.add(row)
        self._s.flush()
        return row

    def has_valid_consent(
        self, farmer_id: uuid.UUID, purpose: ConsentPurpose, channel: Channel, at: datetime
    ) -> bool:
        """Latest ledger entry at or before ``at`` decides. If several rows share the latest
        timestamp, ALL must be grants (a same-instant revocation wins). No row means no consent."""
        at = as_utc(at)
        rows = list(
            self._s.scalars(
                select(Consent)
                .where(
                    Consent.farmer_id == farmer_id,
                    Consent.purpose == purpose,
                    Consent.channel == channel,
                    Consent.recorded_at <= at,
                )
                .order_by(Consent.recorded_at.desc())
            )
        )
        if not rows:
            return False
        latest_ts = as_utc(rows[0].recorded_at)
        latest = [r for r in rows if as_utc(r.recorded_at) == latest_ts]
        if not all(r.granted for r in latest):
            return False
        return all(r.expires_at is None or as_utc(r.expires_at) > at for r in latest)


@dataclass(frozen=True)
class AuditVerification:
    ok: bool
    first_bad_id: int | None = None
    entries_checked: int = 0


def _fmt_ts(ts: datetime) -> str:
    return as_utc(ts).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def compute_entry_hash(
    prev_hash: str,
    ts: datetime,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | None,
    details: dict[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "prev": prev_hash,
            "ts": _fmt_ts(ts),
            "actor": actor,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class AuditLogRepository:
    """Hash-chained audit trail. ``details`` must be JSON-native and should avoid floats
    (JSONB may re-render them), preferring ints and strings."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def append(
        self,
        *,
        ts: datetime,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        details = details or {}
        if self._s.get_bind().dialect.name == "postgresql":
            self._s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _AUDIT_LOCK_KEY})
        prev = self._s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
        prev_hash = prev.entry_hash if prev else GENESIS_HASH
        row = AuditLog(
            ts=as_utc(ts),
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            prev_hash=prev_hash,
            entry_hash=compute_entry_hash(prev_hash, ts, actor, action, entity_type, entity_id, details),
        )
        self._s.add(row)
        self._s.flush()
        return row

    def verify_chain(self) -> AuditVerification:
        prev = GENESIS_HASH
        count = 0
        for row in self._s.scalars(select(AuditLog).order_by(AuditLog.id)):
            expected = compute_entry_hash(
                prev, row.ts, row.actor, row.action, row.entity_type, row.entity_id, row.details
            )
            if row.prev_hash != prev or row.entry_hash != expected:
                return AuditVerification(False, row.id, count)
            prev = row.entry_hash
            count += 1
        return AuditVerification(True, None, count)


class PlanRepository:
    """Repository for district coordination plans."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def create(
        self,
        *,
        district: str,
        plan_date: date,
        strategy: str,
        version: int = 1,
        status: PlanStatus = PlanStatus.ACTIVE,
        parent_plan_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
        objective_value: float | None = None,
        solver_status: str | None = None,
        plan_id: uuid.UUID | None = None,
    ) -> Plan:
        plan = Plan(
            id=plan_id or uuid.uuid4(),
            district=district,
            plan_date=plan_date,
            strategy=strategy,
            version=version,
            status=status,
            parent_plan_id=parent_plan_id,
            payload=payload or {},
            objective_value=objective_value,
            solver_status=solver_status,
        )
        self._s.add(plan)
        self._s.flush()
        return plan

    def get_by_id(self, plan_id: uuid.UUID) -> Plan | None:
        return self._s.get(Plan, plan_id)

    def get_latest_plan(self, district: str, plan_date: date, strategy: str) -> Plan | None:
        stmt = (
            select(Plan)
            .where(
                Plan.district == district,
                Plan.plan_date == plan_date,
                Plan.strategy == strategy,
            )
            .order_by(Plan.version.desc())
            .limit(1)
        )
        return self._s.scalars(stmt).first()

    def supersede(self, plan_id: uuid.UUID) -> bool:
        plan = self._s.get(Plan, plan_id)
        if plan is None:
            return False
        plan.status = PlanStatus.SUPERSEDED
        self._s.flush()
        return True


class ApprovalRepository:
    """Repository for HITL approvals queue."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def create(
        self,
        *,
        kind: str,
        subject_type: str,
        subject_id: uuid.UUID,
        reason: str,
        requested_by: str,
        confidence: float | None = None,
        payload: dict[str, Any] | None = None,
        approval_id: uuid.UUID | None = None,
    ) -> Approval:
        row = Approval(
            id=approval_id or uuid.uuid4(),
            kind=kind,
            subject_type=subject_type,
            subject_id=subject_id,
            status=ApprovalStatus.PENDING,
            reason=reason,
            confidence=confidence,
            requested_by=requested_by,
            payload=payload or {},
        )
        self._s.add(row)
        self._s.flush()
        return row

    def get_by_id(self, approval_id: uuid.UUID) -> Approval | None:
        return self._s.get(Approval, approval_id)

    def resolve(
        self,
        approval_id: uuid.UUID,
        *,
        status: ApprovalStatus,
        decided_by_role: str,
        decision_note: str | None = None,
        decided_at: datetime | None = None,
    ) -> Approval | None:
        row = self._s.get(Approval, approval_id)
        if row is None:
            return None
        row.status = status
        row.decided_by_role = decided_by_role
        row.decision_note = decision_note
        row.decided_at = as_utc(decided_at) if decided_at else as_utc(datetime.now())
        self._s.flush()
        return row

    def list_pending(self, *, subject_type: str | None = None) -> list[Approval]:
        stmt = select(Approval).where(Approval.status == ApprovalStatus.PENDING)
        if subject_type:
            stmt = stmt.where(Approval.subject_type == subject_type)
        return list(self._s.scalars(stmt.order_by(Approval.created_at)).all())
