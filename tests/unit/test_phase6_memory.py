"""Unit tests for Phase 6 Vector Memory, Conversation, and Contract Repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stubbleos.agents.farmer_voice.memory import FarmerMemoryStore, text_to_embedding
from stubbleos.core.types import Channel, ContractStatus, ConversationStatus, Language
from stubbleos.data.models import (
    Base,
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
