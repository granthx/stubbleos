"""Unit tests for MRV agent: evidence hashing, tamper detection, database persistence, and audit log."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from stubbleos.agents.mrv.graph import build_mrv_graph
from stubbleos.agents.mrv.logic import generate_mrv_evidence, verify_evidence_tamper
from stubbleos.agents.mrv.schemas import MrvInput, MrvState
from stubbleos.core.clock import IST
from stubbleos.data.models import AuditLog, Base, ImpactRecord, MrvEvidence
from stubbleos.data.repositories import AuditLogRepository, MrvRepository

TABLES = [MrvEvidence.__table__, ImpactRecord.__table__, AuditLog.__table__]


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"core": None, "pii": None})
    Base.metadata.create_all(engine, tables=TABLES)
    sm = sessionmaker(engine, expire_on_commit=False)
    with sm() as s:
        yield s
    engine.dispose()


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
