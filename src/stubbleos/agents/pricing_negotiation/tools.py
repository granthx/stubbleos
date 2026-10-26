"""Mock tools for Pricing & Negotiation agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


@tool
def compute_dynamic_tariff_mock(area_acres: float, landholding_class: str) -> dict[str, Any]:
    """Mock dynamic tariff computation tool."""
    return {
        "area_acres": area_acres,
        "landholding_class": landholding_class,
        "rate_per_acre_inr": 1200.0,
        "eligible_for_discount": landholding_class in {"marginal", "small"},
    }


def create_pricing_tools() -> list[Any]:
    return [compute_dynamic_tariff_mock]
