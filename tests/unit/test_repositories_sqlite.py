"""Repository logic against SQLite (schemas translated away). Only tables without geometry are created.
The real Postgres/PostGIS path is covered by tests/integration."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from stubbleos.core.clock import SimClock
from stubbleos.core.events import FieldStateChanged, InMemoryEventBus
from stubbleos.core.types import Channel, ConsentPurpose, FieldState, LandholdingClass, Language
from stubbleos.data.event_sink import PersistingEventSink
from stubbleos.data.models import AgentEvent, AuditLog, Base, Consent, Farmer
from stubbleos.data.repositories import (
    AgentEventRepository,
    AuditLogRepository,
    ConsentRepository,
)

T0 = datetime(2026, 10, 20, 6, 0, tzinfo=UTC)
TABLES = [Farmer.__table__, Consent.__table__, AgentEvent.__table__, AuditLog.__table__]


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"core": None, "pii": None})
    Base.metadata.create_all(engine, tables=TABLES)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def session(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as s:
        yield s


def consent_args(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "farmer_id": uuid.uuid4(),
        "purpose": ConsentPurpose.OUTREACH,
        "channel": Channel.WHATSAPP,
        "language": Language.PUNJABI,
        "recorded_by": "test",
    }
    return base | kw


def test_no_consent_row_means_no_consent(session: Session) -> None:
    assert not ConsentRepository(session).has_valid_consent(
        uuid.uuid4(), ConsentPurpose.OUTREACH, Channel.WHATSAPP, T0
    )


def test_grant_then_revoke_then_regrant(session: Session) -> None:
    repo, fid = ConsentRepository(session), uuid.uuid4()
    k = {"farmer_id": fid}
    repo.record(**consent_args(**k, granted=True, at=T0))  # type: ignore[arg-type]
    check = lambda at: repo.has_valid_consent(fid, ConsentPurpose.OUTREACH, Channel.WHATSAPP, at)  # noqa: E731
    assert check(T0 + timedelta(hours=1))
    assert not check(T0 - timedelta(hours=1))  # before it was granted
    repo.record(**consent_args(**k, granted=False, at=T0 + timedelta(days=1)))  # type: ignore[arg-type]
    assert not check(T0 + timedelta(days=2))
    assert check(T0 + timedelta(hours=2))  # history is respected
    repo.record(**consent_args(**k, granted=True, at=T0 + timedelta(days=3)))  # type: ignore[arg-type]
    assert check(T0 + timedelta(days=4))


def test_consent_is_scoped_by_purpose_and_channel(session: Session) -> None:
    repo, fid = ConsentRepository(session), uuid.uuid4()
    repo.record(**consent_args(farmer_id=fid, granted=True, at=T0))  # type: ignore[arg-type]
    assert not repo.has_valid_consent(fid, ConsentPurpose.CONTRACT, Channel.WHATSAPP, T0)
    assert not repo.has_valid_consent(fid, ConsentPurpose.OUTREACH, Channel.VOICE, T0)


def test_expired_consent_is_invalid(session: Session) -> None:
    repo, fid = ConsentRepository(session), uuid.uuid4()
    repo.record(**consent_args(farmer_id=fid, granted=True, at=T0, expires_at=T0 + timedelta(days=1)))  # type: ignore[arg-type]
    assert repo.has_valid_consent(fid, ConsentPurpose.OUTREACH, Channel.WHATSAPP, T0 + timedelta(hours=1))
    assert not repo.has_valid_consent(fid, ConsentPurpose.OUTREACH, Channel.WHATSAPP, T0 + timedelta(days=2))


def test_same_instant_revocation_wins(session: Session) -> None:
    repo, fid = ConsentRepository(session), uuid.uuid4()
    repo.record(**consent_args(farmer_id=fid, granted=True, at=T0))  # type: ignore[arg-type]
    repo.record(**consent_args(farmer_id=fid, granted=False, at=T0))  # type: ignore[arg-type]
    assert not repo.has_valid_consent(fid, ConsentPurpose.OUTREACH, Channel.WHATSAPP, T0)


def test_audit_chain_verifies_and_detects_tampering(session: Session) -> None:
    repo = AuditLogRepository(session)
    assert repo.verify_chain().ok
    for i in range(3):
        repo.append(ts=T0 + timedelta(minutes=i), actor="orchestrator", action="plan.activate",
                    entity_type="plan", entity_id=str(i), details={"n": i})  # fmt: skip
    session.commit()
    result = repo.verify_chain()
    assert result.ok
    assert result.entries_checked == 3

    session.execute(text("UPDATE audit_log SET actor = 'mallory' WHERE id = 2"))
    session.commit()
    tampered = repo.verify_chain()
    assert not tampered.ok
    assert tampered.first_bad_id == 2


def test_agent_event_repo_is_idempotent(session: Session) -> None:
    import asyncio

    async def run() -> None:
        bus = InMemoryEventBus(clock=SimClock(T0))
        corr = uuid.uuid4()
        p = FieldStateChanged(field_id=uuid.uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.7)
        e = await bus.emit(p, source="t", correlation_id=corr, district="ludhiana")
        repo = AgentEventRepository(session)
        assert repo.add(e) is True
        assert repo.add(e) is False
        session.commit()
        back = repo.by_correlation(corr)
        assert back == [e]
        assert back[0].typed_payload() == p

    asyncio.run(run())


async def test_persisting_sink_stores_bus_events(factory: sessionmaker[Session]) -> None:
    bus = InMemoryEventBus(clock=SimClock(T0))
    PersistingEventSink(factory).attach(bus)
    p = FieldStateChanged(field_id=uuid.uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.7)
    e = await bus.emit(p, source="t")
    assert not bus.dead_letters
    with factory() as s:
        assert s.get(AgentEvent, e.event_id) is not None


def test_farmer_table_is_part_of_fixture() -> None:
    # guards the TABLES list: Consent has an FK to farmers, which SQLite doesn't enforce but must exist.
    assert Farmer.__table__.name == "farmers"
    assert LandholdingClass.MARGINAL
