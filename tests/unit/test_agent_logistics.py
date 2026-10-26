"""Unit tests for Logistics agent."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from stubbleos.agents.logistics.graph import build_logistics_graph
from stubbleos.agents.logistics.logic import run_logistics
from stubbleos.agents.logistics.schemas import LogisticsInput, LogisticsState
from stubbleos.agents.logistics.tools import create_logistics_tools
from stubbleos.llm.fake import FakeLLM
from stubbleos.optimization.routing import (
    BuyerDropoff,
    FieldPickup,
    RoutingConfig,
    TruckSpec,
)


@pytest.fixture
def sample_logistics_entities() -> tuple[list[FieldPickup], list[BuyerDropoff], list[TruckSpec]]:
    pickups = [
        FieldPickup(
            field_id=uuid.uuid4(),
            lat=30.25,
            lon=75.80,
            tonnes=12.0,
            moisture_pct=14.0,
            ready_hour=0.0,
            deadline_hour=72.0,
        ),
        FieldPickup(
            field_id=uuid.uuid4(),
            lat=30.28,
            lon=75.83,
            tonnes=8.0,
            moisture_pct=13.5,
            ready_hour=0.0,
            deadline_hour=72.0,
        ),
    ]
    dropoffs = [
        BuyerDropoff(
            buyer_id=uuid.uuid4(),
            lat=30.35,
            lon=75.90,
            max_moisture_pct=16.0,
            capacity_tonnes=50.0,
            open_hour=0.0,
            close_hour=840.0,
        )
    ]
    trucks = [
        TruckSpec(
            truck_id=uuid.uuid4(),
            capacity_tonnes=15.0,
            cost_per_km_inr=45.0,
            co2_kg_per_km=1.42,
            depot_lat=30.20,
            depot_lon=75.75,
            speed_kmh=40.0,
        )
    ]
    return pickups, dropoffs, trucks


@pytest.mark.asyncio
async def test_run_logistics(
    sample_logistics_entities: tuple[list[FieldPickup], list[BuyerDropoff], list[TruckSpec]],
) -> None:
    pickups, dropoffs, trucks = sample_logistics_entities
    fake_llm = FakeLLM(default="Biomass freight routes dispatched efficiently.")

    input_data = LogisticsInput(
        pickups=pickups,
        dropoffs=dropoffs,
        trucks=trucks,
        config=RoutingConfig(time_limit_seconds=0.2),
        request_explanation=True,
    )

    output = await run_logistics(input_data, llm=fake_llm)

    assert "ROUTED" in output.solver_status
    assert output.total_delivered_tonnes > 0
    assert output.total_distance_km > 0
    assert output.total_cost_inr > 0
    assert output.total_co2_kg > 0
    assert "Biomass freight routes" in output.explanation

    # Test without LLM -> fallback summary
    output_no_llm = await run_logistics(input_data, llm=None)
    assert "Generated" in output_no_llm.explanation

    # Test with failing LLM -> fallback summary
    failing_llm = FakeLLM()
    output_failing_llm = await run_logistics(input_data, llm=failing_llm)
    assert "Generated" in output_failing_llm.explanation


@pytest.mark.asyncio
async def test_logistics_graph(
    sample_logistics_entities: tuple[list[FieldPickup], list[BuyerDropoff], list[TruckSpec]],
) -> None:
    pickups, dropoffs, trucks = sample_logistics_entities
    fake_llm = FakeLLM(default="Logistics workflow solved.")
    graph = build_logistics_graph(llm=fake_llm)

    input_data = LogisticsInput(
        pickups=pickups,
        dropoffs=dropoffs,
        trucks=trucks,
        config=RoutingConfig(time_limit_seconds=0.2),
        request_explanation=True,
    )
    state = LogisticsState(input=input_data)
    res = await graph.ainvoke(state, config={"configurable": {"thread_id": "log_test"}})

    assert res["status"] == "completed"
    assert len(res["routes"]) > 0


def test_logistics_tools() -> None:
    tools = create_logistics_tools()
    assert len(tools) == 1
    tool = tools[0]
    res = tool.invoke({"pickup_count": 2, "dropoff_count": 1, "truck_count": 1})
    assert res["status"] == "ready"


def test_logistics_failure_mode_bad_data() -> None:
    """Failure-mode test: Malformed input data is rejected by Pydantic."""
    with pytest.raises(ValidationError):
        LogisticsInput(
            pickups=[],
            dropoffs=[],
            trucks=[],
            illegal_attr=123,  # type: ignore[call-arg]
        )
