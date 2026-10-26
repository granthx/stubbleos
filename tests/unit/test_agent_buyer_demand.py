"""Unit tests for Buyer Demand agent."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from stubbleos.agents.buyer_demand.graph import build_buyer_demand_graph
from stubbleos.agents.buyer_demand.logic import build_order_book
from stubbleos.agents.buyer_demand.schemas import (
    BuyerDemandInput,
    BuyerDemandState,
    BuyerOrderModel,
)
from stubbleos.agents.buyer_demand.tools import create_buyer_demand_tools
from stubbleos.core.types import BuyerType, OrderStatus
from stubbleos.llm.fake import FakeLLM


@pytest.fixture
def sample_orders() -> list[BuyerOrderModel]:
    return [
        BuyerOrderModel(
            order_id=uuid.uuid4(),
            buyer_id=uuid.uuid4(),
            buyer_name="Punjab Biomass Power Plant",
            buyer_type=BuyerType.BIOMASS_PLANT,
            district="Sangrur",
            tonnes_required=100.0,
            tonnes_filled=20.0,
            price_inr_per_tonne=2000.0,
            max_moisture_pct=15.0,
            window_start=date(2026, 10, 15),
            window_end=date(2026, 11, 15),
            status=OrderStatus.OPEN,
        ),
        BuyerOrderModel(
            order_id=uuid.uuid4(),
            buyer_id=uuid.uuid4(),
            buyer_name="Ludhiana Bio-CNG Refinery",
            buyer_type=BuyerType.CBG_PLANT,
            district="Sangrur",
            tonnes_required=50.0,
            tonnes_filled=0.0,
            price_inr_per_tonne=2200.0,
            max_moisture_pct=12.0,
            window_start=date(2026, 10, 20),
            window_end=date(2026, 11, 20),
            status=OrderStatus.OPEN,
        ),
    ]


@pytest.mark.asyncio
async def test_build_order_book(sample_orders: list[BuyerOrderModel]) -> None:
    fake_llm = FakeLLM(default="Commercial demand outlook is strong in Sangrur.")

    input_data = BuyerDemandInput(
        district="Sangrur",
        target_date=date(2026, 10, 25),
        orders=sample_orders,
        request_explanation=True,
    )

    book = await build_order_book(input_data, llm=fake_llm)

    assert book.district == "Sangrur"
    assert book.total_tonnes_demanded == 150.0
    assert book.total_tonnes_filled == 20.0
    assert book.open_tonnes == 130.0
    assert book.min_price_inr_per_tonne == 2000.0
    assert book.max_price_inr_per_tonne == 2200.0
    # Weighted avg: (80*2000 + 50*2200) / 130 = (160000 + 110000) / 130 = 270000 / 130 = ~2076.92
    assert 2075.0 <= book.weighted_avg_price_inr_per_tonne <= 2080.0
    assert "Commercial demand outlook" in book.explanation


@pytest.mark.asyncio
async def test_order_book_moisture_filter(sample_orders: list[BuyerOrderModel]) -> None:
    # Filter for buyers that accept residue with at least 14% moisture
    input_data = BuyerDemandInput(
        district="Sangrur",
        orders=sample_orders,
        max_moisture_pct_filter=14.0,
        request_explanation=False,
    )

    book = await build_order_book(input_data)
    # The 12% moisture limit order should be filtered out
    assert len(book.orders) == 1
    assert book.orders[0].buyer_name == "Punjab Biomass Power Plant"


@pytest.mark.asyncio
async def test_buyer_demand_graph(sample_orders: list[BuyerOrderModel]) -> None:
    fake_llm = FakeLLM(default="Graph order book published.")
    graph = build_buyer_demand_graph(llm=fake_llm)

    input_data = BuyerDemandInput(
        district="Sangrur",
        orders=sample_orders,
        request_explanation=True,
    )
    state = BuyerDemandState(input=input_data)
    res = await graph.ainvoke(state, config={"configurable": {"thread_id": "bd_test"}})

    assert res["status"] == "published"
    assert res["order_book"] is not None
    assert res["order_book"].open_tonnes == 130.0


def test_buyer_demand_tools() -> None:
    tools = create_buyer_demand_tools()
    assert len(tools) == 1
    tool = tools[0]
    res = tool.invoke({"district": "Sangrur"})
    assert res["district"] == "Sangrur"
    assert res["status"] == "ready"


def test_buyer_demand_failure_mode_bad_data() -> None:
    """Failure-mode test: Malformed request is rejected by schema."""
    with pytest.raises(ValidationError):
        BuyerDemandInput(
            district="Sangrur",
            illegal_key="invalid",  # type: ignore[call-arg]
        )


@pytest.mark.asyncio
async def test_buyer_demand_failure_mode_empty_orders() -> None:
    """Failure-mode test: Empty order book returns zero metrics safely."""
    input_data = BuyerDemandInput(
        district="EmptyDistrict",
        orders=[],
        request_explanation=False,
    )
    book = await build_order_book(input_data)
    assert book.total_tonnes_demanded == 0.0
    assert book.open_tonnes == 0.0
    assert book.min_price_inr_per_tonne == 0.0
    assert len(book.orders) == 0
