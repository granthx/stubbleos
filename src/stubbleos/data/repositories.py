"""Repositories for the aggregates: agent events, consent ledger, hash-chained audit log."""

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
from stubbleos.core.types import (
    ApprovalStatus,
    Channel,
    ConsentPurpose,
    ContractStatus,
    ConversationStatus,
    FieldState,
    ImpactRecordStatus,
    Language,
    PlanStatus,
)
from stubbleos.data.models import (
    IMPACT_LABEL,
    AgentEvent,
    Approval,
    AuditLog,
    Consent,
    Contract,
    Conversation,
    ConversationMessage,
    FieldRow,
    ImpactRecord,
    MrvEvidence,
    Plan,
)

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


class MrvRepository:
    """Repository for auditable MRV evidence bundles and indicative impact records."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def record_evidence(
        self,
        *,
        field_id: uuid.UUID,
        evidence_type: str,
        model_version: str,
        inputs: dict[str, Any],
        result: dict[str, Any],
        sha256: str,
        captured_at: datetime,
        is_synthetic: bool = True,
        evidence_id: uuid.UUID | None = None,
    ) -> MrvEvidence:
        row = MrvEvidence(
            id=evidence_id or uuid.uuid4(),
            field_id=field_id,
            evidence_type=evidence_type,
            model_version=model_version,
            inputs=inputs,
            result=result,
            sha256=sha256,
            captured_at=as_utc(captured_at),
            is_synthetic=is_synthetic,
        )
        self._s.add(row)
        self._s.flush()
        return row

    def get_evidence(self, evidence_id: uuid.UUID) -> MrvEvidence | None:
        return self._s.get(MrvEvidence, evidence_id)

    def list_evidence_by_field(self, field_id: uuid.UUID) -> list[MrvEvidence]:
        stmt = select(MrvEvidence).where(MrvEvidence.field_id == field_id).order_by(MrvEvidence.captured_at)
        return list(self._s.scalars(stmt).all())

    def record_impact(
        self,
        *,
        field_id: uuid.UUID,
        season: str,
        burn_avoided: bool,
        area_acres: float,
        est_co2e_kg_avoided: float | None,
        method_note: str = "",
        evidence_ids: list[str] | None = None,
        record_sha256: str,
        is_synthetic: bool = True,
        status: ImpactRecordStatus = ImpactRecordStatus.INDICATIVE,
        record_id: uuid.UUID | None = None,
    ) -> ImpactRecord:
        row = ImpactRecord(
            id=record_id or uuid.uuid4(),
            field_id=field_id,
            season=season,
            status=status,
            label=IMPACT_LABEL,
            burn_avoided=burn_avoided,
            area_acres=area_acres,
            est_co2e_kg_avoided=est_co2e_kg_avoided,
            method_note=method_note,
            evidence_ids=evidence_ids or [],
            record_sha256=record_sha256,
            is_synthetic=is_synthetic,
        )
        self._s.add(row)
        self._s.flush()
        return row

    def get_impact(self, record_id: uuid.UUID) -> ImpactRecord | None:
        return self._s.get(ImpactRecord, record_id)

    def get_impact_by_field_season(self, field_id: uuid.UUID, season: str) -> ImpactRecord | None:
        stmt = select(ImpactRecord).where(ImpactRecord.field_id == field_id, ImpactRecord.season == season)
        return self._s.scalars(stmt).first()


class FieldRepository:
    """Repository for query and state updates on agricultural field rows."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def get_by_id(self, field_id: uuid.UUID) -> FieldRow | None:
        return self._s.get(FieldRow, field_id)

    def update_state(
        self,
        field_id: uuid.UUID,
        *,
        state: FieldState,
        confidence: float,
        updated_at: datetime | None = None,
    ) -> FieldRow | None:
        row = self._s.get(FieldRow, field_id)
        if row is None:
            return None
        row.state = state
        row.state_confidence = confidence
        row.state_updated_at = as_utc(updated_at) if updated_at else as_utc(datetime.now())
        self._s.flush()
        return row

    def list_by_district(self, district: str) -> list[FieldRow]:
        stmt = select(FieldRow).where(FieldRow.district == district)
        return list(self._s.scalars(stmt).all())


# =============================================================================== Dialogue and Contract repositories


class ConversationRepository:
    """Manages conversations (core schema) and turns (pii schema)."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def create_conversation(
        self,
        *,
        farmer_id: uuid.UUID,
        channel: Channel,
        language: Language,
        started_at: datetime | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> Conversation:
        row = Conversation(
            id=conversation_id or uuid.uuid4(),
            farmer_id=farmer_id,
            channel=channel,
            language=language,
            status=ConversationStatus.OPEN,
            started_at=as_utc(started_at) if started_at else as_utc(datetime.now()),
        )
        self._s.add(row)
        self._s.flush()
        return row

    def add_message(
        self,
        *,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        created_at: datetime | None = None,
        message_id: uuid.UUID | None = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            id=message_id or uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=as_utc(created_at) if created_at else as_utc(datetime.now()),
        )
        self._s.add(msg)
        self._s.flush()
        return msg

    def get_conversation(self, conversation_id: uuid.UUID) -> Conversation | None:
        return self._s.get(Conversation, conversation_id)

    def get_messages(self, conversation_id: uuid.UUID) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.asc())
        )
        return list(self._s.scalars(stmt).all())

    def close_conversation(
        self,
        conversation_id: uuid.UUID,
        *,
        status: ConversationStatus = ConversationStatus.COMPLETED,
        outcome: dict[str, Any] | None = None,
        ended_at: datetime | None = None,
    ) -> Conversation | None:
        row = self.get_conversation(conversation_id)
        if row is None:
            return None
        row.status = status
        row.outcome = outcome
        row.ended_at = as_utc(ended_at) if ended_at else as_utc(datetime.now())
        self._s.flush()
        return row


class ContractRepository:
    """Manages negotiated straw supply and baling contracts."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def create_contract(
        self,
        *,
        field_id: uuid.UUID,
        farmer_id: uuid.UUID,
        price_inr_per_tonne: float,
        tonnes_agreed: float,
        order_id: uuid.UUID | None = None,
        buyer_id: uuid.UUID | None = None,
        terms: dict[str, Any] | None = None,
        contract_sha256: str | None = None,
        status: ContractStatus = ContractStatus.DRAFT,
        contract_id: uuid.UUID | None = None,
    ) -> Contract:
        contract_terms = terms or {}
        sha = (
            contract_sha256
            or hashlib.sha256(
                f"{field_id}:{farmer_id}:{buyer_id}:{price_inr_per_tonne}:{tonnes_agreed}".encode()
            ).hexdigest()
        )

        row = Contract(
            id=contract_id or uuid.uuid4(),
            order_id=order_id,
            field_id=field_id,
            farmer_id=farmer_id,
            buyer_id=buyer_id,
            terms=contract_terms,
            price_inr_per_tonne=price_inr_per_tonne,
            tonnes_agreed=tonnes_agreed,
            status=status,
            contract_sha256=sha,
            created_at=as_utc(datetime.now()),
        )
        self._s.add(row)
        self._s.flush()
        return row

    def get_by_id(self, contract_id: uuid.UUID) -> Contract | None:
        return self._s.get(Contract, contract_id)

    def mark_accepted(self, contract_id: uuid.UUID, accepted_at: datetime | None = None) -> Contract | None:
        row = self.get_by_id(contract_id)
        if row is None:
            return None
        row.status = ContractStatus.ACCEPTED
        row.accepted_at = as_utc(accepted_at) if accepted_at else as_utc(datetime.now())
        self._s.flush()
        return row

    def list_by_farmer(self, farmer_id: uuid.UUID) -> list[Contract]:
        stmt = select(Contract).where(Contract.farmer_id == farmer_id).order_by(Contract.created_at.desc())
        return list(self._s.scalars(stmt).all())

    def list_by_buyer(self, buyer_id: uuid.UUID) -> list[Contract]:
        stmt = select(Contract).where(Contract.buyer_id == buyer_id).order_by(Contract.created_at.desc())
        return list(self._s.scalars(stmt).all())


@dataclass
class DocumentMatch:
    doc_id: str
    text: str
    similarity: float
    metadata: dict[str, Any]


class VectorMemoryRepository:
    """Document and conversation semantic memory store.

    Uses cosine similarity for semantic retrieval. Operates in-memory or backed by
    pgvector embeddings when available.
    """

    def __init__(self) -> None:
        self._documents: dict[str, dict[str, Any]] = {}

    def add_document(
        self,
        doc_id: str,
        text: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._documents[doc_id] = {
            "text": text,
            "embedding": embedding,
            "metadata": metadata or {},
        }

    def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        min_similarity: float = 0.0,
    ) -> list[DocumentMatch]:
        if not self._documents or not query_embedding:
            return []

        import numpy as np

        q_vec = np.array(query_embedding, dtype=float)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        matches: list[DocumentMatch] = []
        for doc_id, doc in self._documents.items():
            d_vec = np.array(doc["embedding"], dtype=float)
            d_norm = np.linalg.norm(d_vec)
            sim = 0.0 if d_norm == 0 else float(np.dot(q_vec, d_vec) / (q_norm * d_norm))

            if sim >= min_similarity:
                matches.append(
                    DocumentMatch(
                        doc_id=doc_id,
                        text=doc["text"],
                        similarity=round(sim, 4),
                        metadata=doc["metadata"],
                    )
                )

        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches[:top_k]

    def clear(self) -> None:
        self._documents.clear()
