"""Consolidated core test suite for StubbleOS."""

from __future__ import annotations

# ==============================================================================
# Section: test_config.py
# ==============================================================================
import pytest
from pydantic import ValidationError

from stubbleos.core.config import Settings


def make(**kw: object) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[arg-type]


def test_defaults_are_safe() -> None:
    s = make()
    assert s.llm_provider == "auto"
    assert s.whatsapp_enabled is False
    assert s.otel_enabled is False


def test_prod_requires_real_salt() -> None:
    with pytest.raises(ValidationError):
        make(env="prod", llm_provider="anthropic", anthropic_api_key="k")


def test_prod_rejects_fake_llm() -> None:
    with pytest.raises(ValidationError):
        make(env="prod", pseudonym_salt="x" * 32, llm_provider="fake")


def test_anthropic_requires_key() -> None:
    with pytest.raises(ValidationError):
        make(llm_provider="anthropic")


def test_groq_requires_key() -> None:
    with pytest.raises(ValidationError):
        make(llm_provider="groq")


def test_contact_hours_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        make(contact_hours_start=19, contact_hours_end=8)


def test_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUBBLEOS_LOG_LEVEL", "DEBUG")
    assert make().log_level == "DEBUG"


def test_unprefixed_anthropic_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    s = make()
    assert s.anthropic_api_key is not None
    assert s.anthropic_api_key.get_secret_value() == "sk-test"
    assert "sk-test" not in repr(s)


def test_unprefixed_groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    s = make()
    assert s.groq_api_key is not None
    assert s.groq_api_key.get_secret_value() == "gsk-test"
    assert "gsk-test" not in repr(s)


# ==============================================================================
# Section: test_clock.py
# ==============================================================================
from datetime import UTC, datetime, timedelta

from stubbleos.core.clock import IST, SimClock, as_utc


def test_sim_clock_advances_and_refuses_backwards() -> None:
    c = SimClock(datetime(2026, 10, 20, tzinfo=UTC))
    c.advance_days(1.5)
    assert c.now() == datetime(2026, 10, 21, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="SimClock cannot move backwards"):
        c.advance(timedelta(seconds=-1))
    with pytest.raises(ValueError, match="SimClock cannot move backwards"):
        c.set(datetime(2026, 1, 1, tzinfo=UTC))


def test_naive_start_rejected() -> None:
    with pytest.raises(ValueError, match="naive datetime not allowed"):
        SimClock(datetime(2026, 10, 20))


def test_ist_offset_and_as_utc() -> None:
    local = datetime(2026, 10, 20, 8, 0, tzinfo=IST)
    assert as_utc(local) == datetime(2026, 10, 20, 2, 30, tzinfo=UTC)
    assert as_utc(datetime(2026, 10, 20, 2, 30)).tzinfo is UTC


# ==============================================================================
# Section: test_privacy.py
# ==============================================================================

from stubbleos.core.privacy import REDACTED, Pseudonymizer, mask_phone, redact, redact_text


@pytest.mark.parametrize(
    "raw",
    ["9876543210", "+91 9876543210", "+919876543210", "91-9876543210", "0091 9876543210"],
)
def test_phone_numbers_redacted(raw: str) -> None:
    assert redact_text(f"call {raw} now") == f"call {REDACTED} now"


def test_aadhaar_and_email_redacted() -> None:
    out = redact_text("id 2345 6789 0123 mail a.b@example.com")
    assert "2345" not in out
    assert "example.com" not in out


def test_non_pii_numbers_survive() -> None:
    assert (
        redact_text("field 12 has 4.5 acres, deadline in 14 days")
        == "field 12 has 4.5 acres, deadline in 14 days"
    )


def test_sensitive_keys_blanked_recursively() -> None:
    out = redact({"farmer_name": "X", "nested": [{"phone_e164": "1", "ok": 5}], "district": "Ludhiana"})
    assert out["farmer_name"] == REDACTED
    assert out["nested"][0]["phone_e164"] == REDACTED
    assert out["nested"][0]["ok"] == 5
    assert out["district"] == "Ludhiana"


def test_mask_phone() -> None:
    assert mask_phone("+919876543210").endswith("43210")
    assert "98765" not in mask_phone("+919876543210")
    assert mask_phone("12") == REDACTED


def test_pseudonymizer_properties() -> None:
    a, b = Pseudonymizer("salt-a"), Pseudonymizer("salt-b")
    assert a.pseudonymize("farmer", "42") == a.pseudonymize("farmer", "42")
    assert a.pseudonymize("farmer", "42") != a.pseudonymize("operator", "42")
    assert a.pseudonymize("farmer", "42") != b.pseudonymize("farmer", "42")
    with pytest.raises(ValueError, match="salt"):
        Pseudonymizer("")


# ==============================================================================
# Section: test_retry.py
# ==============================================================================
import asyncio

import pytest

from stubbleos.core.retry import RetryExhausted, retry_async


class Flaky:
    def __init__(self, failures: int, exc: type[Exception] = ConnectionError) -> None:
        self.failures, self.exc, self.calls = failures, exc, 0

    async def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc("boom")
        return "ok"


async def test_succeeds_after_retries_with_exponential_delays() -> None:
    delays: list[float] = []

    async def fake_sleep(d: float) -> None:
        delays.append(d)

    fn = Flaky(2)
    assert await retry_async(fn, attempts=3, base_delay=1.0, jitter=0.0, sleep=fake_sleep) == "ok"
    assert delays == [1.0, 2.0]


async def test_exhaustion_wraps_last_error() -> None:
    async def no_sleep(_: float) -> None: ...

    with pytest.raises(RetryExhausted) as ei:
        await retry_async(Flaky(10), attempts=2, sleep=no_sleep)
    assert ei.value.attempts == 2
    assert isinstance(ei.value.last_error, ConnectionError)


async def test_non_retryable_propagates_immediately() -> None:
    fn = Flaky(5, ValueError)
    with pytest.raises(ValueError, match="boom"):
        await retry_async(fn, attempts=3, retry_on=(ConnectionError,))
    assert fn.calls == 1


async def test_timeout_is_retryable() -> None:
    async def no_sleep(_: float) -> None: ...

    async def slow() -> str:
        await asyncio.sleep(1)
        return "late"

    with pytest.raises(RetryExhausted) as ei:
        await retry_async(slow, attempts=2, timeout_s=0.01, retry_on=(TimeoutError,), sleep=no_sleep)
    assert isinstance(ei.value.last_error, TimeoutError)


# ==============================================================================
# Section: test_events.py
# ==============================================================================
from uuid import uuid4

import pytest

from stubbleos.core.events import (
    Event,
    EventPayload,
    FieldStateChanged,
    UnknownEventType,
    get_payload_type,
    register_event,
    registered_event_types,
)
from stubbleos.core.types import FieldState

TS = datetime(2026, 10, 20, tzinfo=UTC)


def test_roundtrip_through_json() -> None:
    payload = FieldStateChanged(
        field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.9, evidence=["fixture"]
    )
    event = Event.create(payload, source="field_monitor", ts=TS)
    restored = Event.model_validate_json(event.model_dump_json())
    assert restored == event
    assert restored.typed_payload() == payload


def test_unknown_type_raises() -> None:
    event = Event(event_id=uuid4(), event_type="nope.nothing", source="x", ts=TS, payload={})
    with pytest.raises(UnknownEventType):
        event.typed_payload()


def test_payload_validation_is_strict() -> None:
    with pytest.raises(ValidationError):
        FieldStateChanged(field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=1.5)
    with pytest.raises(ValidationError):
        FieldStateChanged(  # type: ignore[call-arg]
            field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.5, surprise=1
        )


def test_naive_timestamp_rejected() -> None:
    p = FieldStateChanged(field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.5)
    with pytest.raises(ValueError, match="naive datetime not allowed"):
        Event.create(p, source="x", ts=datetime(2026, 1, 1))


def test_duplicate_registration_conflicts() -> None:
    with pytest.raises(ValueError, match="already registered"):

        @register_event("field.state_changed")
        class Other(EventPayload):
            x: int = 0


def test_registry_contents() -> None:
    assert "field.state_changed" in registered_event_types()
    assert get_payload_type("approval.requested").event_type == "approval.requested"


# ==============================================================================
# Section: test_event_bus.py
# ==============================================================================

import pytest

from stubbleos.core.events import (
    EventBusError,
    InMemoryEventBus,
    ReplanTriggered,
)
from stubbleos.core.ids import SeededUUIDFactory
from stubbleos.core.types import ReplanReason


def fsc() -> FieldStateChanged:
    return FieldStateChanged(field_id=uuid4(), previous=None, new=FieldState.CLEARED, confidence=0.8)


async def test_delivery_order_and_patterns(bus: InMemoryEventBus) -> None:
    seen: list[str] = []

    async def a(e: Event) -> None:
        seen.append(f"a:{e.event_type}")

    async def b(e: Event) -> None:
        seen.append(f"b:{e.event_type}")

    bus.subscribe("field.*", a)
    bus.subscribe("*", b)
    await bus.emit(fsc(), source="t")
    await bus.emit(ReplanTriggered(district="d", reason=ReplanReason.DAILY), source="t")
    assert seen == ["a:field.state_changed", "b:field.state_changed", "b:plan.replan_triggered"]


async def test_handler_error_is_isolated_and_recorded(bus: InMemoryEventBus) -> None:
    got: list[Event] = []

    async def bad(_: Event) -> None:
        raise RuntimeError("kaput")

    async def good(e: Event) -> None:
        got.append(e)

    bus.subscribe("*", bad)
    bus.subscribe("*", good)
    await bus.emit(fsc(), source="t")
    assert len(got) == 1
    assert len(bus.dead_letters) == 1
    assert "kaput" in bus.dead_letters[0].error


async def test_raise_on_handler_error(clock: SimClock) -> None:
    strict = InMemoryEventBus(clock=clock, raise_on_handler_error=True)

    async def bad(_: Event) -> None:
        raise RuntimeError("kaput")

    strict.subscribe("*", bad)
    with pytest.raises(RuntimeError):
        await strict.emit(fsc(), source="t")


async def test_cancel_subscription(bus: InMemoryEventBus) -> None:
    got: list[Event] = []

    async def h(e: Event) -> None:
        got.append(e)

    sub = bus.subscribe("*", h)
    await bus.emit(fsc(), source="t")
    sub.cancel()
    await bus.emit(fsc(), source="t")
    assert len(got) == 1


async def test_unknown_event_rejected_on_publish(bus: InMemoryEventBus, clock: SimClock) -> None:
    bad = Event(event_id=uuid4(), event_type="made.up", source="t", ts=clock.now(), payload={})
    with pytest.raises(UnknownEventType):
        await bus.publish(bad)
    assert bus.history == []


async def test_runaway_loop_is_stopped(bus: InMemoryEventBus) -> None:
    async def loop(_: Event) -> None:
        await bus.emit(fsc(), source="loop")

    bus.subscribe("field.*", loop)
    with pytest.raises(EventBusError):
        await bus.emit(fsc(), source="t")


async def test_emit_stamps_clock_and_is_deterministic(clock: SimClock) -> None:
    p = fsc()
    b1 = InMemoryEventBus(clock=clock, id_factory=SeededUUIDFactory(7))
    b2 = InMemoryEventBus(clock=clock, id_factory=SeededUUIDFactory(7))
    e1 = await b1.emit(p, source="t", district="ludhiana")
    e2 = await b2.emit(p, source="t", district="ludhiana")
    assert e1 == e2
    assert e1.ts == clock.now()
    assert e1.district == "ludhiana"


# ==============================================================================
# Section: test_models_schema.py
# ==============================================================================
"""Static checks on the ORM metadata: the PII boundary and required tables. No database needed."""

import pytest

from stubbleos.data.models import CORE, CORE_TABLES_REQUIRED, IMPACT_LABEL, PII, Base

FORBIDDEN_IN_CORE = ("full_name", "phone", "email", "address", "aadhaar", "village_name", "content")


def tables(schema: str) -> dict[str, object]:
    return {t.name: t for t in Base.metadata.tables.values() if t.schema == schema}


def test_every_table_is_in_core_or_pii() -> None:
    assert {t.schema for t in Base.metadata.tables.values()} == {CORE, PII}


def test_required_tables_exist() -> None:
    assert set(tables(CORE)) >= CORE_TABLES_REQUIRED


def test_pii_tables_are_exactly_the_identity_tables() -> None:
    assert set(tables(PII)) == {
        "farmer_identities",
        "operator_identities",
        "buyer_contacts",
        "conversation_messages",
    }


@pytest.mark.parametrize("name", sorted(CORE_TABLES_REQUIRED))
def test_no_pii_columns_in_core(name: str) -> None:
    table = Base.metadata.tables[f"{CORE}.{name}"]
    bad = [c.name for c in table.columns if any(f in c.name.lower() for f in FORBIDDEN_IN_CORE)]
    assert bad == []


def test_impact_records_cannot_be_unlabeled() -> None:
    table = Base.metadata.tables[f"{CORE}.impact_records"]
    names = {c.name for c in table.constraints if c.name}
    assert any("label_disclaimer" in n for n in names)
    assert "not registry-verified" in IMPACT_LABEL


def test_synthetic_flag_on_evidence_and_impact() -> None:
    for name in ("mrv_evidence", "impact_records"):
        assert "is_synthetic" in Base.metadata.tables[f"{CORE}.{name}"].columns


# ==============================================================================
# Section: test_memory_repositories.py
# ==============================================================================
"""Unit tests for Vector Memory, Conversation, and Contract Repositories."""


import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stubbleos.agents.farmer_voice.memory import FarmerMemoryStore, text_to_embedding
from stubbleos.core.types import Channel, ContractStatus, ConversationStatus, Language
from stubbleos.data.models import (
    Contract,
    Conversation,
    ConversationMessage,
    Farmer,
)
from stubbleos.data.repositories import (
    ContractRepository,
    ConversationRepository,
    VectorMemoryRepository,
)


def test_text_to_embedding_properties() -> None:
    vec1 = text_to_embedding("Super Seeder CRM subsidy in Punjab")
    vec2 = text_to_embedding("Super Seeder CRM subsidy in Punjab")
    vec3 = text_to_embedding("Completely unrelated text about electronics")

    assert len(vec1) == 32
    assert vec1 == vec2  # Deterministic!

    import numpy as np

    v1 = np.array(vec1)
    v2 = np.array(vec2)
    v3 = np.array(vec3)

    sim_identical = float(np.dot(v1, v2))
    sim_different = float(np.dot(v1, v3))

    assert round(sim_identical, 2) == 1.0
    assert sim_different < sim_identical


def test_farmer_memory_store_semantic_search() -> None:
    store = FarmerMemoryStore()

    # Search for CRM subsidy on super seeder
    results = store.search_policy("What is the government subsidy on Super Seeder?", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert "Super Seeder" in top.text or "subsidy" in top.text.lower()
    assert top.similarity > 0.0

    # Search for burn penalties
    results_penalty = store.search_policy("What is the penalty for burning stubble?", top_k=2)
    assert len(results_penalty) > 0
    assert any("penalty" in r.text.lower() or "compensation" in r.text.lower() for r in results_penalty)


def test_vector_memory_repository_edge_cases() -> None:
    repo = VectorMemoryRepository()

    # Empty search
    assert repo.search_similar([0.1, 0.2]) == []

    # Zero vector search
    repo.add_document("d1", "hello", [1.0, 0.0])
    assert repo.search_similar([0.0, 0.0]) == []

    # Add and retrieve with metadata
    repo.add_document("d2", "world", [0.0, 1.0], metadata={"tag": "greet"})
    matches = repo.search_similar([0.0, 1.0], top_k=1)
    assert len(matches) == 1
    assert matches[0].doc_id == "d2"
    assert matches[0].metadata["tag"] == "greet"


def test_conversation_and_contract_repositories_sqlite() -> None:
    # Use SQLite in-memory engine with schema translation
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"core": None, "pii": None})
    tables = [
        Farmer.__table__,
        Conversation.__table__,
        ConversationMessage.__table__,
        Contract.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)

    with Session(engine) as session:
        # Seed a farmer row for foreign keys
        f_id = uuid.uuid4()
        farmer = Farmer(
            id=f_id,
            pseudonym="f_pseudonym_test",
            district="sangrur",
            landholding_class="marginal",
            total_area_acres=2.0,
            trust_score=0.9,
            preferred_language=Language.PUNJABI,
        )
        session.add(farmer)
        session.flush()

        conv_repo = ConversationRepository(session)
        contract_repo = ContractRepository(session)

        b_id = uuid.uuid4()
        fld_id = uuid.uuid4()

        # 1. Conversation Lifecycle
        conv = conv_repo.create_conversation(
            farmer_id=f_id,
            channel=Channel.WHATSAPP,
            language=Language.PUNJABI,
        )
        assert conv.status == ConversationStatus.OPEN

        # Add messages
        conv_repo.add_message(
            conversation_id=conv.id,
            role="farmer",
            content="ਮੈਨੂੰ ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ",
        )
        conv_repo.add_message(
            conversation_id=conv.id,
            role="agent",
            content="ਤੁਹਾਡਾ ਕਿੰਨੇ ਏਕੜ ਖੇਤ ਹੈ?",
        )

        history = conv_repo.get_messages(conv.id)
        assert len(history) == 2
        assert history[0].content == "ਮੈਨੂੰ ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ"
        assert history[1].role == "agent"

        # Close conversation
        closed = conv_repo.close_conversation(
            conv.id,
            status=ConversationStatus.COMPLETED,
            outcome={"booked": True, "acres": 4.0},
        )
        assert closed is not None
        assert closed.status == ConversationStatus.COMPLETED
        assert closed.outcome["booked"] is True

        # 2. Contract Lifecycle
        contract = contract_repo.create_contract(
            field_id=fld_id,
            farmer_id=f_id,
            buyer_id=b_id,
            price_inr_per_tonne=1700.0,
            tonnes_agreed=80.0,
            status=ContractStatus.OFFERED,
        )
        assert contract.price_inr_per_tonne == 1700.0
        assert len(contract.contract_sha256) == 64

        accepted = contract_repo.mark_accepted(contract.id)
        assert accepted is not None
        assert accepted.status == ContractStatus.ACCEPTED
        assert accepted.accepted_at is not None

        # Query listings
        farmer_contracts = contract_repo.list_by_farmer(f_id)
        assert len(farmer_contracts) == 1
        buyer_contracts = contract_repo.list_by_buyer(b_id)
        assert len(buyer_contracts) == 1


# ==============================================================================
# Section: test_repositories_sqlite.py
# ==============================================================================
"""Repository logic against SQLite (schemas translated away). Only tables without geometry are created.
The real Postgres/PostGIS path is covered by tests/integration."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from stubbleos.core.types import ConsentPurpose, LandholdingClass
from stubbleos.data.event_sink import PersistingEventSink
from stubbleos.data.models import AgentEvent, AuditLog, Consent
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


# ==============================================================================
# Section: test_channels.py
# ==============================================================================
"""Unit tests for Messaging Channels & Router."""


from datetime import datetime

import pytest

from stubbleos.channels.ivr import IVRChannel
from stubbleos.channels.mock import MockChannel
from stubbleos.channels.models import OutboundMessage
from stubbleos.channels.router import ChannelRouter
from stubbleos.channels.whatsapp import WhatsAppChannel


@pytest.mark.asyncio
async def test_whatsapp_webhook_parsing_and_sending() -> None:
    wa = WhatsAppChannel()

    # Inbound Meta Cloud API text message webhook
    meta_webhook = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "type": "text",
                                    "text": {"body": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    inbound = wa.parse_inbound(meta_webhook)
    assert inbound.sender_id == "919876543210"
    assert inbound.text == "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ"
    assert inbound.channel == Channel.WHATSAPP

    # Outbound WhatsApp message delivery
    msg = OutboundMessage(
        recipient_id="+919876543210",
        channel=Channel.WHATSAPP,
        text="ਤੁਹਾਡੀ ਮਸ਼ੀਨ ਬੁਕਿੰਗ ਦੀ ਪੁਸ਼ਟੀ ਹੋ ਗਈ ਹੈ।",
        quick_replies=["ਹਾਂ", "ਨਹੀਂ"],
    )
    res = await wa.send_message(msg)
    assert res.success is True
    assert res.status == "delivered"
    assert len(wa.sent_payloads) == 1
    assert wa.sent_payloads[0]["to"] == "+919876543210"


@pytest.mark.asyncio
async def test_ivr_call_dispatch_and_dtmf() -> None:
    ivr = IVRChannel()

    # Outbound call
    msg = OutboundMessage(
        recipient_id="+919876543210",
        channel=Channel.VOICE,
        text="ਮਸ਼ੀਨ ਬੁਕਿੰਗ ਲਈ 1 ਦਬਾਓ, ਰੱਦ ਕਰਨ ਲਈ 2 ਦਬਾਓ।",
        audio_uri="s3://stubbleos-audio/ivr_prompt_01.wav",
    )
    res = await ivr.send_message(msg)
    assert res.success is True
    assert len(ivr.call_history) == 1

    # Inbound DTMF digit webhook
    dtmf_payload = {
        "From": "+919876543210",
        "Digits": "1",
    }
    inbound = ivr.parse_inbound(dtmf_payload)
    assert inbound.text == "DTMF:1"
    assert inbound.channel == Channel.VOICE


@pytest.mark.asyncio
async def test_channel_router_consent_enforcement() -> None:
    clock = SimClock(start=datetime(2026, 10, 30, 11, 0, tzinfo=IST))  # 11:00 AM (daytime)
    event_bus = InMemoryEventBus(clock=clock)
    mock_ch = MockChannel(clock=clock)

    # Class mimicking ConsentRepository for unit testing
    class FakeConsentRepo:
        def __init__(self, consents: set[tuple[uuid.UUID, ConsentPurpose, Channel]] | None = None) -> None:
            self.consents = consents or set()

        def has_valid_consent(
            self, farmer_id: uuid.UUID, purpose: ConsentPurpose, channel: Channel, at: datetime
        ) -> bool:
            return (farmer_id, purpose, channel) in self.consents

    f_consented = uuid.uuid4()
    f_unconsented = uuid.uuid4()

    consent_repo = FakeConsentRepo(consents={(f_consented, ConsentPurpose.OUTREACH, Channel.MOCK)})

    router = ChannelRouter(
        channels={Channel.MOCK: mock_ch},
        consent_repo=consent_repo,  # type: ignore[arg-type]
        event_bus=event_bus,
        clock=clock,
    )

    # 1. Allowed dispatch for consented farmer
    msg_allowed = OutboundMessage(
        recipient_id="f_consented_recipient",
        channel=Channel.MOCK,
        text="Machine arrives today at 2 PM",
    )
    res1 = await router.dispatch_outbound(
        msg_allowed,
        farmer_id=f_consented,
        conversation_id=uuid.uuid4(),
        purpose=ConsentPurpose.OUTREACH,
    )
    assert res1.success is True
    assert res1.status == "delivered"

    # 2. Blocked dispatch for unconsented farmer
    msg_blocked = OutboundMessage(
        recipient_id="f_unconsented_recipient",
        channel=Channel.MOCK,
        text="Special machinery discount offer",
    )
    res2 = await router.dispatch_outbound(
        msg_blocked,
        farmer_id=f_unconsented,
        conversation_id=uuid.uuid4(),
        purpose=ConsentPurpose.OUTREACH,
    )
    assert res2.success is False
    assert res2.status == "blocked_no_consent"


@pytest.mark.asyncio
async def test_channel_router_quiet_hours_policy() -> None:
    # 23:30 IST is during quiet hours (21:00 - 07:00 IST)
    night_time = datetime(2026, 10, 30, 23, 30, tzinfo=IST)
    clock = SimClock(start=night_time)
    mock_ch = MockChannel(clock=clock)

    router = ChannelRouter(
        channels={Channel.MOCK: mock_ch},
        clock=clock,
        enforce_quiet_hours=True,
    )

    # Normal priority message is delayed during quiet hours
    msg_normal = OutboundMessage(
        recipient_id="test_farmer",
        channel=Channel.MOCK,
        text="Routine weekly update",
        priority="normal",
    )
    res_normal = await router.dispatch_outbound(msg_normal)
    assert res_normal.success is False
    assert res_normal.status == "quiet_hours_delayed"

    # Critical priority message (e.g. fire hazard emergency) bypasses quiet hours
    msg_critical = OutboundMessage(
        recipient_id="test_farmer",
        channel=Channel.MOCK,
        text="EMERGENCY: Urgent harvest fire risk in your sector!",
        priority="critical",
    )
    res_critical = await router.dispatch_outbound(msg_critical)
    assert res_critical.success is True
    assert res_critical.status == "delivered"


# ==============================================================================
# Section: test_api_health.py
# ==============================================================================
from fastapi.testclient import TestClient

from stubbleos.api.app import create_app


def make_health_client(checks: dict[str, object]) -> TestClient:
    settings = Settings(_env_file=None, env="test", llm_provider="fake")  # type: ignore[call-arg]
    return TestClient(create_app(settings, readiness_checks=checks))  # type: ignore[arg-type]


def test_healthz() -> None:
    assert make_health_client({}).get("/healthz").json()["status"] == "ok"


def test_ready_when_all_checks_pass() -> None:
    r = make_health_client({"database": lambda: True, "redis": lambda: True}).get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_degraded_when_a_check_fails_or_raises() -> None:
    def boom() -> bool:
        raise ConnectionError("down")

    r = make_health_client({"database": lambda: True, "redis": boom}).get("/readyz")
    assert r.status_code == 503
    assert r.json()["checks"] == {"database": True, "redis": False}


def test_metrics_endpoint_exposes_prometheus_text() -> None:
    r = make_health_client({}).get("/metrics")
    assert r.status_code == 200
    assert "stubbleos_events_published_total" in r.text or "python_info" in r.text


# ==============================================================================
# Section: test_api_v1.py
# ==============================================================================
"""Unit tests for REST API v1 endpoints and WebSockets."""


import pytest


@pytest.fixture
def client() -> TestClient:
    settings = Settings(_env_file=None, env="test", llm_provider="fake")  # type: ignore[call-arg]
    app = create_app(settings, readiness_checks={})
    return TestClient(app)


def test_list_and_filter_fields(client: TestClient) -> None:
    res = client.get("/api/v1/fields?district=sangrur")
    assert res.status_code == 200
    fields = res.json()
    assert len(fields) > 0
    assert fields[0]["district"] == "sangrur"

    # Filter by state
    res_cleared = client.get(f"/api/v1/fields?district=sangrur&state={FieldState.CLEARED.value}")
    assert res_cleared.status_code == 200
    for f in res_cleared.json():
        assert f["state"] == FieldState.CLEARED.value


def test_register_and_get_field(client: TestClient) -> None:
    f_id = uuid.uuid4()
    req = {
        "farmer_id": str(f_id),
        "district": "sangrur",
        "village_code": "PB-SAN-NEW",
        "area_acres": 4.5,
        "center_lat": 30.260,
        "center_lon": 75.860,
        "crop_type": "paddy",
    }
    # Register field with admin key
    res = client.post("/api/v1/fields", json=req, headers={"X-API-Key": "stubbleos-admin-key"})
    assert res.status_code == 201
    created = res.json()
    assert created["village_code"] == "PB-SAN-NEW"
    assert created["area_acres"] == 4.5

    # Fetch created field
    res_get = client.get(f"/api/v1/fields/{created['id']}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == created["id"]


def test_list_machines(client: TestClient) -> None:
    res = client.get("/api/v1/machines?district=sangrur")
    assert res.status_code == 200
    machines = res.json()
    assert len(machines) > 0
    assert "machine_type" in machines[0]
    assert "capacity_acres_per_day" in machines[0]


def test_plans_and_replan_trigger(client: TestClient) -> None:
    res = client.get("/api/v1/plans?district=sangrur")
    assert res.status_code == 200
    plans = res.json()
    assert len(plans) > 0
    assert plans[0]["strategy"] == "stubbleos_centralized_cpsat"

    # Trigger emergency replan
    replan_req = {
        "district": "sangrur",
        "reason": "Unexpected rain forecast change",
        "emergency": True,
    }
    res_replan = client.post(
        "/api/v1/plans/replan",
        json=replan_req,
        headers={"X-API-Key": "stubbleos-admin-key"},
    )
    assert res_replan.status_code == 200
    new_plan = res_replan.json()
    assert "emergency" in new_plan["strategy"]


def test_bookings_create_and_confirm(client: TestClient) -> None:
    req = {
        "farmer_id": str(uuid.uuid4()),
        "field_id": str(uuid.uuid4()),
        "service_type": "in_situ_sowing",
        "machine_type": "super_seeder",
        "target_date": "2026-11-03",
        "channel": "whatsapp",
    }
    res = client.post("/api/v1/bookings", json=req)
    assert res.status_code == 201
    booking = res.json()
    assert booking["status"] == "proposed"

    # Confirm booking
    res_conf = client.post(f"/api/v1/bookings/{booking['id']}/confirm")
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "confirmed"


def test_approvals_listing_and_resolution(client: TestClient) -> None:
    res = client.get("/api/v1/approvals")
    assert res.status_code == 200
    approvals = res.json()
    assert len(approvals) > 0
    a_id = approvals[0]["id"]

    # Resolve approval
    res_resolve = client.post(
        f"/api/v1/approvals/{a_id}/resolve",
        json={"decision": "approved", "note": "Verified by district officer"},
        headers={"X-API-Key": "stubbleos-operator-key"},
    )
    assert res_resolve.status_code == 200
    resolved = res_resolve.json()
    assert resolved["status"] == "approved"
    assert resolved["decided_by_role"] == "operator"


def test_contract_bidding_and_acceptance(client: TestClient) -> None:
    b_id = uuid.uuid4()
    bid = {
        "buyer_id": str(b_id),
        "order_id": str(uuid.uuid4()),
        "price_per_tonne_inr": 1750.0,
        "tonnes": 50.0,
        "delivery_term": "ex_field",
        "moisture_max_pct": 14.0,
    }
    res = client.post(
        "/api/v1/contracts/negotiate",
        json=bid,
        headers={"X-API-Key": "stubbleos-buyer-key"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["counter_offer"]["accepted"] is True
    assert data["contract"] is not None

    contract_id = data["contract"]["id"]
    res_accept = client.post(
        f"/api/v1/contracts/{contract_id}/accept",
        headers={"X-API-Key": "stubbleos-buyer-key"},
    )
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "accepted"


def test_channel_webhooks(client: TestClient) -> None:
    # WhatsApp inbound webhook
    wa_payload = {
        "sender_id": "+919876543210",
        "text": "ਮੈਨੂੰ ਮਸ਼ੀਨ ਚਾਹੀਦੀ ਹੈ",
    }
    res_wa = client.post("/api/v1/channels/webhook/whatsapp", json=wa_payload)
    assert res_wa.status_code == 200
    assert res_wa.json()["status"] == "received"

    # IVR inbound webhook
    ivr_payload = {
        "From": "+919876543210",
        "Digits": "1",
    }
    res_ivr = client.post("/api/v1/channels/webhook/voice", json=ivr_payload)
    assert res_ivr.status_code == 200
    assert res_ivr.json()["status"] == "received"


def test_mrv_and_district_summary(client: TestClient) -> None:
    # MRV endpoint
    fld_id = uuid.uuid4()
    res_mrv = client.get(f"/api/v1/mrv/{fld_id}")
    assert res_mrv.status_code == 200
    proof = res_mrv.json()
    assert "co2e_avoided_tonnes" in proof
    assert len(proof["bundle_sha256"]) == 64
    assert proof["impact_label"] == "indicative impact record (not registry-verified)"

    # District summary endpoint
    res_dist = client.get("/api/v1/district-summary/sangrur")
    assert res_dist.status_code == 200
    summary = res_dist.json()
    assert summary["district"] == "sangrur"
    assert summary["total_fields"] >= 0
    assert summary["indicative_co2e_avoided_tonnes"] >= 0.0


def test_websocket_connection_and_echo(client: TestClient) -> None:
    with client.websocket_connect("/ws/district/sangrur") as websocket:
        websocket.send_text("ping")
        data = websocket.receive_json()
        assert data["type"] == "ack"
        assert data["received"] == "ping"


# ==============================================================================
# Section: test_geo_indices.py
# ==============================================================================
"""Unit tests for remote sensing vegetation, soil, and burn indices with hand-computed verification."""


import numpy as np
import pytest
from shapely.geometry import Polygon

from stubbleos.geo.indices import (
    compute_bsi,
    compute_nbr,
    compute_ndvi,
    detect_index_change,
)
from stubbleos.geo.raster import (
    compute_zonal_stats,
    create_synthetic_field_raster,
)


def test_ndvi_hand_computed_values() -> None:
    """Tests NDVI calculation on small 2x2 raster with hand-computed exact values.

    Formula: (NIR - Red) / (NIR + Red)
    """
    # 2x2 pixel grid
    nir = np.array([[0.70, 0.35], [0.80, 0.00]], dtype=np.float64)
    red = np.array([[0.10, 0.30], [0.20, 0.00]], dtype=np.float64)

    # Hand-computed:
    # (0, 0): (0.7 - 0.1) / (0.7 + 0.1) = 0.6 / 0.8 = 0.750000 (Dense green canopy)
    # (0, 1): (0.35 - 0.3) / (0.35 + 0.3) = 0.05 / 0.65 = 0.076923 (Harvested / stubble)
    # (1, 0): (0.8 - 0.2) / (0.8 + 0.2) = 0.6 / 1.0 = 0.600000 (Vegetation)
    # (1, 1): 0 / 0 = 0.000000 (Zero denominator handling)
    expected = np.array(
        [[0.75, 0.05 / 0.65], [0.60, 0.0]],
        dtype=np.float64,
    )

    result = compute_ndvi(nir, red)
    assert np.allclose(result, expected, atol=1e-6)
    assert result[0, 0] == pytest.approx(0.75, abs=1e-5)
    assert result[0, 1] == pytest.approx(0.076923, abs=1e-5)
    assert result[1, 1] == 0.0


def test_bsi_hand_computed_values() -> None:
    """Tests Bare Soil Index on 2x2 raster with hand-computed exact values.

    Formula: ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))
    """
    swir = np.array([[0.20, 0.50], [0.60, 0.00]], dtype=np.float64)
    red = np.array([[0.10, 0.30], [0.25, 0.00]], dtype=np.float64)
    nir = np.array([[0.70, 0.35], [0.15, 0.00]], dtype=np.float64)
    blue = np.array([[0.05, 0.15], [0.10, 0.00]], dtype=np.float64)

    # Hand-computed:
    # (0, 0): soil = 0.2+0.1=0.3; veg = 0.7+0.05=0.75;
    #         (0.3 - 0.75) / (0.3 + 0.75) = -0.45 / 1.05 = -0.428571 (Dense crop)
    # (0, 1): soil = 0.5+0.3=0.8; veg = 0.35+0.15=0.5;
    #         (0.8 - 0.5) / (0.8 + 0.5) = 0.3 / 1.3 = 0.230769 (Bare cleared soil)
    # (1, 0): soil = 0.6+0.25=0.85; veg = 0.15+0.1=0.25;
    #         (0.85 - 0.25) / (0.85 + 0.25) = 0.6 / 1.1 = 0.545455 (Dry tilled soil)
    # (1, 1): 0 / 0 = 0.000000 (Zero denominator)
    expected = np.array(
        [
            [-0.45 / 1.05, 0.3 / 1.3],
            [0.6 / 1.1, 0.0],
        ],
        dtype=np.float64,
    )

    result = compute_bsi(swir, red, nir, blue)
    assert np.allclose(result, expected, atol=1e-6)
    assert result[0, 0] == pytest.approx(-0.428571, abs=1e-5)
    assert result[0, 1] == pytest.approx(0.230769, abs=1e-5)
    assert result[1, 0] == pytest.approx(0.545455, abs=1e-5)


def test_nbr_hand_computed_values() -> None:
    """Tests Normalized Burn Ratio: (NIR - SWIR) / (NIR + SWIR)."""
    nir = np.array([[0.75, 0.15]], dtype=np.float64)
    swir = np.array([[0.25, 0.60]], dtype=np.float64)

    # (0, 0): (0.75 - 0.25) / (0.75 + 0.25) = 0.5 / 1.0 = 0.500000 (Unburned)
    # (0, 1): (0.15 - 0.60) / (0.15 + 0.60) = -0.45 / 0.75 = -0.600000 (Burned stubble)
    expected = np.array([[0.50, -0.60]], dtype=np.float64)
    result = compute_nbr(nir, swir)
    assert np.allclose(result, expected, atol=1e-6)


def test_detect_index_change() -> None:
    """Tests temporal change detection between pre-harvest and post-harvest."""
    pre_ndvi = np.array([0.75, 0.70])
    post_ndvi = np.array([0.25, 0.68])

    abs_change, rel_drop = detect_index_change(pre_ndvi, post_ndvi)

    # Pixel 0: dropped from 0.75 to 0.25 (abs: -0.50, rel_drop: 0.50 / 0.75 = 0.666667)
    assert abs_change[0] == pytest.approx(-0.50, abs=1e-6)
    assert rel_drop[0] == pytest.approx(0.666667, abs=1e-5)

    # Pixel 1: small variation 0.70 to 0.68 (abs: -0.02, rel_drop: 0.02 / 0.70 = 0.028571)
    assert abs_change[1] == pytest.approx(-0.02, abs=1e-6)
    assert rel_drop[1] == pytest.approx(0.028571, abs=1e-5)


def test_compute_zonal_stats_and_synthetic_raster() -> None:
    """Tests zonal statistics aggregation over synthetic raster within polygon bounds."""
    grid = create_synthetic_field_raster(
        shape=(10, 10),
        bounds=(75.80, 30.20, 75.90, 30.30),
        ndvi_base=0.72,
        seed=42,
    )

    ndvi_arr = compute_ndvi(grid.bands["nir"], grid.bands["red"])

    # Define polygon matching the central area of the raster
    field_poly = Polygon(
        [
            (75.82, 30.22),
            (75.88, 30.22),
            (75.88, 30.28),
            (75.82, 30.28),
            (75.82, 30.22),
        ]
    )

    stats = compute_zonal_stats(ndvi_arr, grid.bounds, field_poly)
    assert stats["count"] > 0
    assert 0.65 <= stats["mean"] <= 0.80
    assert stats["min"] <= stats["mean"] <= stats["max"]
    assert stats["std"] >= 0.0

    # Non-intersecting polygon returns zero stats
    outside_poly = Polygon([(76.5, 31.0), (76.6, 31.0), (76.6, 31.1), (76.5, 31.0)])
    outside_stats = compute_zonal_stats(ndvi_arr, grid.bounds, outside_poly)
    assert outside_stats["count"] == 0.0
    assert outside_stats["mean"] == 0.0


# ==============================================================================
# Section: test_geo_clients.py
# ==============================================================================
"""Unit tests for STAC, FIRMS, and Open-Meteo clients testing caching, retries, timeouts, and fallbacks."""


from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from stubbleos.geo.client import CachingGeoClient
from stubbleos.geo.firms import NasaFirmsClient
from stubbleos.geo.stac import Sentinel2StacClient
from stubbleos.geo.weather import OpenMeteoClient


@pytest.fixture
def geo_client() -> CachingGeoClient:
    return CachingGeoClient()


@pytest.mark.asyncio
async def test_geo_client_cache_hit(geo_client: CachingGeoClient) -> None:
    """Verifies that a subsequent call with identical parameters returns cached data."""
    test_url = "https://mock.geo.api/v1/test"
    params = {"district": "Sangrur"}

    # Seed the cache directly using client cache key
    key = geo_client.make_cache_key(test_url, params)
    geo_client._set_cache(key, {"key": "cached_val"}, ttl=3600.0)

    res = await geo_client.get_json(test_url, params=params)
    assert res.source == "cache"
    assert res.is_fallback is False
    assert res.data == {"key": "cached_val"}
    assert res.confidence_penalty == 0.0


@pytest.mark.asyncio
async def test_geo_client_timeout_and_fallback(geo_client: CachingGeoClient) -> None:
    """Verifies that a remote timeout degrades gracefully to the committed offline fixture."""
    test_url = "https://unreachable.stac.test/v1/search"

    # Mock httpx.AsyncClient.get to raise TimeoutError
    with patch("httpx.AsyncClient.get", side_effect=TimeoutError("Request timed out")):
        res = await geo_client.get_json(
            test_url,
            fixture_fallback_name="sentinel2_stac_sangrur.json",
        )

    assert res.source == "fixture"
    assert res.is_fallback is True
    assert res.confidence_penalty > 0.0
    assert "features" in res.data
    assert len(res.data["features"]) > 0


@pytest.mark.asyncio
async def test_geo_client_retry_with_backoff(geo_client: CachingGeoClient) -> None:
    """Verifies retry behavior on transient HTTP 500 error."""
    test_url = "https://flaky.api/v1/data"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "retried": True}
    mock_resp.raise_for_status = lambda: None

    attempts = 0

    async def flaky_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise httpx.HTTPStatusError("500 Internal Error", request=None, response=None)
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=flaky_get):
        res = await geo_client.get_json(test_url, ttl_seconds=60.0)

    assert attempts == 2
    assert res.data["status"] == "ok"
    assert res.source == "network"


@pytest.mark.asyncio
async def test_sentinel2_stac_client_fallback() -> None:
    """Tests Sentinel-2 STAC client fallback to committed fixture in offline environment."""
    client = Sentinel2StacClient()
    bbox = (75.70, 30.15, 76.15, 30.45)

    result = await client.search_scenes(
        bbox=bbox,
        start_date=date(2026, 10, 15),
        end_date=date(2026, 10, 26),
    )

    assert len(result.scenes) >= 2
    assert result.scenes[0].scene_id.startswith("S2")
    assert "red" in result.scenes[0].assets
    assert "nir" in result.scenes[0].assets
    # Should flag fallback when real external STAC API is offline
    assert result.is_fallback is True
    assert result.confidence_penalty > 0.0


@pytest.mark.asyncio
async def test_nasa_firms_client_and_spatial_filtering() -> None:
    """Tests NASA FIRMS client query, fallback, and spatial polygon intersection."""
    firms_client = NasaFirmsClient()
    bbox = (75.70, 30.15, 76.15, 30.45)

    search_res = await firms_client.get_active_fires(
        bbox=bbox,
        start_date=date(2026, 10, 20),
        end_date=date(2026, 10, 25),
    )

    assert len(search_res.hits) >= 3
    assert search_res.is_fallback is True

    # Spatial intersection: polygon enclosing the first hit at (lat 30.2451, lon 75.8342)
    hit_poly = Polygon(
        [
            (75.830, 30.240),
            (75.840, 30.240),
            (75.840, 30.250),
            (75.830, 30.250),
            (75.830, 30.240),
        ]
    )

    intersecting = NasaFirmsClient.filter_hits_for_polygon(
        hit_poly,
        search_res.hits,
        min_confidence_pct=50.0,
    )
    assert len(intersecting) == 1
    assert intersecting[0].latitude == pytest.approx(30.2451, abs=1e-4)

    # Distant polygon with no hits
    distant_poly = Polygon(
        [
            (75.50, 30.00),
            (75.51, 30.00),
            (75.51, 30.01),
            (75.50, 30.01),
            (75.50, 30.00),
        ]
    )
    assert len(NasaFirmsClient.filter_hits_for_polygon(distant_poly, search_res.hits)) == 0


@pytest.mark.asyncio
async def test_open_meteo_client_forecast_and_workability() -> None:
    """Tests Open-Meteo weather client forecast parsing and safe operating window workability under offline fallback."""
    weather_client = OpenMeteoClient()

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Network offline")):
        res = await weather_client.get_forecast(
            latitude=30.24,
            longitude=75.84,
            start_date=date(2026, 10, 20),
            end_date=date(2026, 10, 26),
        )

    assert res.is_fallback is True
    assert res.confidence_penalty > 0.0
    assert len(res.forecasts) == 7
    # Day 0 (2026-10-20) has 0 rain, wind 12.2 km/h -> workable
    assert res.forecasts[0].is_workable is True

    # Day 3 (2026-10-23) has 12.5mm rain > threshold 2.0mm -> unworkable
    assert res.forecasts[3].precipitation_mm == pytest.approx(12.5, abs=0.1)
    assert res.forecasts[3].is_workable is False

    # Day 4 (2026-10-24) has 8.4mm rain -> unworkable
    assert res.forecasts[4].is_workable is False

    # Day 5 (2026-10-25) has 0 rain -> workable
    assert res.forecasts[5].is_workable is True


# ==============================================================================
# Section: test_geo_failure_modes.py
# ==============================================================================
"""Failure mode tests for components and agents."""


import pytest

from stubbleos.agents.field_monitor.schemas import (
    FieldObservationRequest,
)
from stubbleos.agents.mrv.schemas import MrvInput
from stubbleos.agents.weather_window.schemas import WeatherWindowInput


def test_failure_mode_field_monitor_bad_coordinates() -> None:
    """Field Monitor failure mode: Malformed polygon coordinates or extra keys rejected."""
    with pytest.raises(ValidationError):
        FieldObservationRequest(
            field_id=uuid.uuid4(),
            extra_illegal_key="fail",  # type: ignore[call-arg]
        )


def test_failure_mode_weather_window_invalid_date_ordering() -> None:
    """Weather Window failure mode: Invalid date format rejected."""
    with pytest.raises(ValidationError):
        WeatherWindowInput(
            district="Sangrur",
            start_date="not_a_date",  # type: ignore[arg-type]
            end_date="not_a_date",  # type: ignore[arg-type]
        )


def test_failure_mode_mrv_negative_or_zero_area() -> None:
    """MRV failure mode: Non-positive area rejected."""
    with pytest.raises(ValidationError):
        MrvInput(field_id=uuid.uuid4(), area_acres=0.0)

    with pytest.raises(ValidationError):
        MrvInput(field_id=uuid.uuid4(), area_acres=-10.0)


@pytest.mark.asyncio
async def test_failure_mode_missing_fixture_raises_error() -> None:
    """Geo client failure mode: Missing offline fixture raises FileNotFoundError."""
    client = CachingGeoClient()
    with pytest.raises(FileNotFoundError):
        client.load_fixture("non_existent_fixture.json")


@pytest.mark.asyncio
async def test_failure_mode_remote_failure_without_fixture_propagates() -> None:
    """Geo client failure mode: Remote failure without fallback fixture propagates exception."""
    client = CachingGeoClient()
    with (
        patch("httpx.AsyncClient.get", side_effect=TimeoutError("Network down")),
        pytest.raises(RetryExhausted),
    ):
        await client.get_json("https://broken.api/v1", fixture_fallback_name=None)


# ==============================================================================
# Section: test_prompts.py
# ==============================================================================
import pytest

from stubbleos.llm.prompts import PromptError, PromptNotFound, PromptRegistry, PromptTemplate


def reg() -> PromptRegistry:
    r = PromptRegistry()
    r.register(PromptTemplate(name="offer", version=1, template="Offer $price for $tonnes t"))
    r.register(PromptTemplate(name="offer", version=2, template='{"p": "$price"} t=$tonnes'))
    r.register(PromptTemplate(name="offer", version=2, language=Language.HINDI, template="HI $price $tonnes"))
    return r


def test_latest_version_by_default_and_json_braces_are_safe() -> None:
    out = reg().render("offer", price="100", tonnes="2")
    assert out.ref == "offer@v2"
    assert out.text == '{"p": "100"} t=2'


def test_language_specific_then_fallback() -> None:
    r = reg()
    assert r.render("offer", language=Language.HINDI, price="1", tonnes="2").ref == "offer@v2:hi"
    assert r.render("offer", language=Language.PUNJABI, price="1", tonnes="2").ref == "offer@v2"


def test_pinned_version() -> None:
    assert reg().render("offer", version=1, price="1", tonnes="2").text == "Offer 1 for 2 t"


def test_strict_variables() -> None:
    r = reg()
    with pytest.raises(PromptError):
        r.render("offer", price="1")
    with pytest.raises(PromptError):
        r.render("offer", price="1", tonnes="2", typo="x")


def test_duplicates_invalid_and_missing() -> None:
    r = reg()
    with pytest.raises(PromptError):
        r.register(PromptTemplate(name="offer", version=1, template="again"))
    with pytest.raises(PromptError):
        r.register(PromptTemplate(name="bad", version=1, template="cost $"))
    with pytest.raises(PromptNotFound):
        r.get("absent")


# ==============================================================================
# Section: test_fake_llm.py
# ==============================================================================
import re

import pytest
from pydantic import BaseModel

from stubbleos.llm.base import (
    LLMRequest,
    LLMStructuredOutputError,
    extract_json,
    generate_structured_via_text,
)
from stubbleos.llm.fake import FakeLLM, FakeLLMNoResponse


class Offer(BaseModel):
    price: int
    accept: bool


def req(text: str, purpose: str = "t") -> LLMRequest:
    return LLMRequest.simple(text, purpose=purpose)


async def test_queue_then_rules_then_default() -> None:
    llm = FakeLLM(default="dflt").queue("first").when("rain", "umbrella").when(re.compile(r"^hi"), "hello")
    assert (await llm.generate(req("anything"))).text == "first"
    assert (await llm.generate(req("will it rain"))).text == "umbrella"
    assert (await llm.generate(req("hi there"))).text == "hello"
    assert (await llm.generate(req("zzz"))).text == "dflt"
    assert len(llm.calls) == 4
    assert llm.meter.calls == 4


async def test_callable_rule_and_callable_response() -> None:
    llm = FakeLLM().when(lambda r: r.purpose == "p", lambda r: f"echo:{r.full_text()}")
    assert (await llm.generate(req("x", purpose="p"))).text == "echo:x"


async def test_no_response_fails_loudly() -> None:
    with pytest.raises(FakeLLMNoResponse):
        await FakeLLM().generate(req("x"))


async def test_structured_from_model_dict_and_json_string() -> None:
    llm = FakeLLM().queue(
        Offer(price=1, accept=True),
        {"price": 2, "accept": False},
        '```json\n{"price": 3, "accept": true}\n```',
    )
    assert (await llm.generate_structured(req("a"), Offer)).price == 1
    assert (await llm.generate_structured(req("b"), Offer)).price == 2
    assert (await llm.generate_structured(req("c"), Offer)).price == 3


async def test_structured_invalid_raises() -> None:
    llm = FakeLLM().queue({"price": "not-a-number"}, "no json here")
    with pytest.raises(LLMStructuredOutputError):
        await llm.generate_structured(req("a"), Offer)
    with pytest.raises(LLMStructuredOutputError):
        await llm.generate_structured(req("b"), Offer)


async def test_text_based_structured_retries_with_feedback() -> None:
    llm = FakeLLM().queue("sorry, I cannot", '{"price": 9, "accept": true}')
    out = await generate_structured_via_text(llm, req("offer?"), Offer, max_attempts=2)
    assert out == Offer(price=9, accept=True)
    assert len(llm.calls) == 2
    assert "JSON Schema" in (llm.calls[0].system or "")
    assert "invalid" in llm.calls[1].messages[-1].content


async def test_text_based_structured_gives_up() -> None:
    llm = FakeLLM(default="nope")
    with pytest.raises(LLMStructuredOutputError):
        await generate_structured_via_text(llm, req("x"), Offer, max_attempts=2)
    assert len(llm.calls) == 2


def test_extract_json_handles_prose_and_fences() -> None:
    assert extract_json('Sure! {"a": 1} hope that helps') == '{"a": 1}'
    with pytest.raises(LLMStructuredOutputError):
        extract_json("no braces")


# ==============================================================================
# Section: test_groq_llm.py
# ==============================================================================
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, SecretStr

from stubbleos.llm.base import LLMError
from stubbleos.llm.factory import build_llm
from stubbleos.llm.groq_client import GroqLLM


class SampleOutput(BaseModel):
    summary: str
    count: int


def _mock_completion(content: str, prompt_tokens: int = 10, completion_tokens: int = 20) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


async def test_groq_generate_success() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _mock_completion("Hello from Groq")

    llm = GroqLLM(
        api_key=SecretStr("gsk-test"),
        model="llama-3.3-70b-versatile",
        client=mock_client,
    )
    req = LLMRequest.simple("test message", system="You are an assistant")
    res = await llm.generate(req)

    assert res.text == "Hello from Groq"
    assert res.provider == "groq"
    assert res.model == "llama-3.3-70b-versatile"
    assert res.usage.input_tokens == 10
    assert res.usage.output_tokens == 20
    assert llm.meter.input_tokens == 10
    assert llm.meter.output_tokens == 20
    assert llm.meter.calls == 1

    mock_client.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_client.chat.completions.create.await_args.kwargs
    assert call_kwargs["messages"][0] == {"role": "system", "content": "You are an assistant"}
    assert call_kwargs["messages"][1] == {"role": "user", "content": "test message"}


async def test_groq_generate_structured_success() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _mock_completion('{"summary": "cleared", "count": 42}')

    llm = GroqLLM(
        api_key=SecretStr("gsk-test"),
        model="llama-3.3-70b-versatile",
        client=mock_client,
    )
    req = LLMRequest.simple("give summary")
    structured = await llm.generate_structured(req, SampleOutput)

    assert structured.summary == "cleared"
    assert structured.count == 42


async def test_groq_generate_error_raises_llm_error() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("API unavailable")

    llm = GroqLLM(
        api_key=SecretStr("gsk-test"),
        model="llama-3.3-70b-versatile",
        client=mock_client,
    )
    with pytest.raises(LLMError, match="RuntimeError: API unavailable"):
        await llm.generate(LLMRequest.simple("hello"))


def test_factory_builds_groq_llm() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="auto",
        groq_api_key="gsk-test",
    )
    client = build_llm(settings)
    assert isinstance(client, GroqLLM)
    assert client.provider == "groq"
    assert client.model == "llama-3.3-70b-versatile"


# ==============================================================================
# Section: test_model_selection_eval.py
# ==============================================================================
"""Unit tests for Phase 3 Model Selection & Evaluation assets."""


import json
from pathlib import Path

import yaml

from stubbleos.evals.model_bench import (
    evaluate_dataset_with_candidate,
    paired_bootstrap_ci,
)


def test_evaluation_datasets_exist_and_are_valid() -> None:
    datasets = [
        ("evals/datasets/smoke.jsonl", 30),
        ("evals/datasets/golden_core.jsonl", 100),
        ("evals/datasets/adversarial_redteam.jsonl", 50),
    ]
    for path_str, min_count in datasets:
        path = Path(path_str)
        assert path.exists(), f"Dataset missing: {path_str}"
        items = []
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                assert line.strip(), f"Empty line {line_no} in {path_str}"
                item = json.loads(line)
                assert "id" in item
                assert "text" in item
                assert "language" in item
                items.append(item)
        assert len(items) >= min_count, f"{path_str} has {len(items)} items, expected at least {min_count}"


def test_metrics_yaml_is_valid() -> None:
    metrics_path = Path("evals/metrics.yaml")
    assert metrics_path.exists()
    with open(metrics_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert "metrics" in data
    assert "segments" in data
    assert "intent_accuracy" in data["metrics"]
    assert "slot_f1_score" in data["metrics"]
    assert "policy_guard_compliance" in data["metrics"]
    assert "adversarial_attack_success_rate" in data["metrics"]


def test_paired_bootstrap_ci_computation() -> None:
    data = [1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0]
    mean, lo, hi = paired_bootstrap_ci(data, n_boot=1000, seed=42)
    assert 0.75 <= mean <= 0.85
    assert 0.50 <= lo <= mean
    assert mean <= hi <= 1.0


def test_model_bench_smoke_run() -> None:
    smoke_path = Path("evals/datasets/smoke.jsonl")
    result = evaluate_dataset_with_candidate("heuristic_baseline", smoke_path, seed=42)
    assert result["candidate"] == "heuristic_baseline"
    assert result["sample_count"] == 30
    assert 0.0 <= result["intent_accuracy"]["mean"] <= 1.0
    assert 0.0 <= result["slot_f1"]["mean"] <= 1.0
    assert result["p95_latency_ms"] >= 0.0


def test_eval_benchmark_results_exist() -> None:
    p = Path("evals/results/phase3_model_selection.json")
    assert p.exists()
