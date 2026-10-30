"""Vector memory and policy document indexing for Farmer Voice agent."""

from __future__ import annotations

import hashlib
import re

import numpy as np

from stubbleos.data.repositories import DocumentMatch, VectorMemoryRepository

DEFAULT_POLICY_DOCUMENTS = [
    {
        "doc_id": "crm_subsidy_super_seeder",
        "text": "Government of Punjab provides 50% individual subsidy and 80% cooperative (CHC) subsidy on Super Seeders and Happy Seeders under the Crop Residue Management (CRM) scheme.",
        "metadata": {"category": "subsidy", "machine": "super_seeder", "state": "punjab"},
    },
    {
        "doc_id": "ex_situ_baling_guidelines",
        "text": "For ex-situ straw collection, baling is suitable for dry straw (<14% moisture). Custom Hiring Centres dispatch rakes and balers within 48 hours of combine harvesting.",
        "metadata": {"category": "guideline", "machine": "baler", "moisture_max": 14},
    },
    {
        "doc_id": "burn_penalties_and_fire_bans",
        "text": "National Green Tribunal (NGT) and CAQM impose environmental compensation of ₹2,500 to ₹15,000 for stubble burning. Red entries in revenue records restrict future farm credit.",
        "metadata": {"category": "regulatory", "penalty_min_inr": 2500, "penalty_max_inr": 15000},
    },
    {
        "doc_id": "smallholder_cross_subsidy_fpo",
        "text": "Marginal (<2.5 acres) and small (<5.0 acres) farmers receive guaranteed 25% to 35% discount on machinery tariffs funded through StubbleOS cooperative pool.",
        "metadata": {"category": "equity", "discount_pct": 25},
    },
]


def text_to_embedding(text: str, dim: int = 32) -> list[float]:
    """Generates a deterministic normalized embedding vector from text using token hashing."""
    vec = np.zeros(dim, dtype=float)
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return vec.tolist()

    for token in tokens:
        idx = int(hashlib.sha256(token.encode()).hexdigest(), 16) % dim
        vec[idx] += 1.0

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tolist()


class FarmerMemoryStore:
    """Semantic document and conversation memory store for Farmer Voice."""

    def __init__(self, repo: VectorMemoryRepository | None = None) -> None:
        self.repo = repo or VectorMemoryRepository()
        self._seed_default_policies()

    def _seed_default_policies(self) -> None:
        for doc in DEFAULT_POLICY_DOCUMENTS:
            emb = text_to_embedding(doc["text"])  # type: ignore[arg-type]
            self.repo.add_document(
                doc_id=str(doc["doc_id"]),
                text=str(doc["text"]),
                embedding=emb,
                metadata=doc["metadata"],  # type: ignore[arg-type]
            )

    def search_policy(self, query: str, top_k: int = 2) -> list[DocumentMatch]:
        emb = text_to_embedding(query)
        return self.repo.search_similar(emb, top_k=top_k)

    def index_conversation_turn(self, conversation_id: str, turn_text: str, role: str) -> None:
        doc_id = f"conv_{conversation_id}_{hashlib.sha256(turn_text.encode()).hexdigest()[:8]}"
        emb = text_to_embedding(turn_text)
        self.repo.add_document(
            doc_id=doc_id,
            text=turn_text,
            embedding=emb,
            metadata={"conversation_id": conversation_id, "role": role},
        )
