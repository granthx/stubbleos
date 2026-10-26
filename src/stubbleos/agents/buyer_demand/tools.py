"""Tools for Buyer Demand agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from stubbleos.llm.base import LLMClient


def create_buyer_demand_tools(llm: LLMClient | None = None) -> list[Any]:
    """Factory to instantiate buyer demand tools."""

    @tool
    def query_order_book(district: str) -> dict[str, Any]:
        """Queries active industrial buyer off-take orders and prices for a district."""
        return {
            "district": district,
            "status": "ready",
        }

    return [query_order_book]
