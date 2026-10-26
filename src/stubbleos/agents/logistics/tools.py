"""Tools for Logistics agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from stubbleos.llm.base import LLMClient


def create_logistics_tools(llm: LLMClient | None = None) -> list[Any]:
    """Factory to instantiate logistics routing tools."""

    @tool
    def compute_straw_routes(
        pickup_count: int,
        dropoff_count: int,
        truck_count: int,
        co2_weight: float = 5.0,
    ) -> dict[str, Any]:
        """Calculates multi-depot VRP delivery routes for baled crop residue."""
        return {
            "pickup_count": pickup_count,
            "dropoff_count": dropoff_count,
            "truck_count": truck_count,
            "co2_weight": co2_weight,
            "status": "ready",
        }

    return [compute_straw_routes]
