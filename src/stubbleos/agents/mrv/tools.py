"""Mock tools for MRV agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


@tool
def generate_mrv_evidence_mock(field_id_str: str, area_acres: float) -> dict[str, Any]:
    """Mock MRV proof generation tool."""
    return {
        "field_id": field_id_str,
        "area_acres": area_acres,
        "co2e_kg_avoided": area_acres * 2628.0,
        "signed_proof": "mock_sha256_hash",
        "label": "indicative impact record (not registry-verified)",
    }


def create_mrv_tools() -> list[Any]:
    return [generate_mrv_evidence_mock]
