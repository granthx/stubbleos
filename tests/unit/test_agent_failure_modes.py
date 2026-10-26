"""Failure mode tests for every StubbleOS agent (bad data, timeouts, low confidence)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from stubbleos.agents.buyer_demand.schemas import BuyerDemandInput
from stubbleos.agents.farmer_voice.schemas import FarmerVoiceInput
from stubbleos.agents.field_monitor.schemas import FieldMonitorInput
from stubbleos.agents.logistics.schemas import LogisticsInput
from stubbleos.agents.machine_scheduler.logic import run_machine_scheduler
from stubbleos.agents.machine_scheduler.schemas import MachineSchedulerInput
from stubbleos.agents.mrv.schemas import MrvInput
from stubbleos.agents.orchestrator.logic import calculate_plan_confidence
from stubbleos.agents.orchestrator.schemas import OrchestratorInput
from stubbleos.agents.policy_guard.schemas import PolicyCheckRequest
from stubbleos.agents.pricing_negotiation.schemas import PricingInput
from stubbleos.agents.weather_window.schemas import WeatherWindowInput
from stubbleos.core.types import LandholdingClass, MachineType, ServiceType
from stubbleos.optimization.scheduler import JobRequest, MachineResource, SchedulerConfig


def test_failure_mode_orchestrator_bad_data() -> None:
    """Orchestrator failure mode: Malformed input data rejected by strict schema."""
    with pytest.raises(ValidationError):
        OrchestratorInput(
            district="Sangrur",
            plan_date=date(2026, 10, 20),
            illegal_field_name="forbidden_payload",  # type: ignore[call-arg]
        )


def test_failure_mode_orchestrator_low_confidence_detection() -> None:
    """Orchestrator failure mode: Extreme machine shortage produces low confidence score."""
    # 10 jobs pending, 0 assigned, solver infeasible -> confidence should be severely penalized
    conf = calculate_plan_confidence(
        assignments=[],
        total_jobs=10,
        solver_status="INFEASIBLE",
    )
    assert conf < 0.30


@pytest.mark.asyncio
async def test_failure_mode_machine_scheduler_timeout() -> None:
    """Machine Scheduler failure mode: Short time limit yields best feasible or fallback without crashing."""
    jobs = [
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=4.0,
            earliest_start_hour=0.0,
            deadline_hour=48.0,
            center_lat=30.25,
            center_lon=75.80,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        )
    ]
    machines = [
        MachineResource(
            machine_id=uuid.uuid4(),
            machine_type=MachineType.HAPPY_SEEDER,
            capacity_acres_per_hour=1.5,
            hourly_cost_inr=800.0,
            current_lat=30.24,
            current_lon=75.79,
            available_from_hour=0.0,
        )
    ]
    # Ultra-short timeout (0.001s / 1ms)
    cfg = SchedulerConfig(time_limit_seconds=0.001)
    inp = MachineSchedulerInput(
        jobs=jobs,
        machines=machines,
        mode="cpsat",
        config=cfg,
        request_explanation=False,
    )
    output = await run_machine_scheduler(inp)
    # Solver must return gracefully with status indicator
    assert output.solver_status in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "FALLBACK_GREEDY"}


def test_failure_mode_machine_scheduler_bad_data() -> None:
    """Machine Scheduler failure mode: Invalid machine type rejected."""
    with pytest.raises(ValidationError):
        MachineSchedulerInput(
            jobs=[],
            machines=[],
            mode="invalid_algorithm",  # type: ignore[arg-type]
        )


def test_failure_mode_logistics_bad_data() -> None:
    """Logistics failure mode: Missing required fields rejected."""
    with pytest.raises(ValidationError):
        LogisticsInput()  # type: ignore[call-arg]


def test_failure_mode_buyer_demand_bad_data() -> None:
    """Buyer Demand failure mode: Extra unknown fields rejected."""
    with pytest.raises(ValidationError):
        BuyerDemandInput(district="Sangrur", unknown_key=True)  # type: ignore[call-arg]


def test_failure_mode_policy_guard_bad_data() -> None:
    """Policy Guard failure mode: Extra attributes rejected."""
    with pytest.raises(ValidationError):
        PolicyCheckRequest(action_ref="act_1", invalid_prop="fail")  # type: ignore[call-arg]


def test_failure_mode_field_monitor_bad_data() -> None:
    """Field Monitor failure mode: Negative observation window rejected if constrained or invalid type."""
    with pytest.raises(ValidationError):
        FieldMonitorInput(district="Sangrur", field_ids=["not-a-uuid"])  # type: ignore[list-item]


def test_failure_mode_weather_window_bad_data() -> None:
    """Weather Window failure mode: Invalid date format rejected."""
    with pytest.raises(ValidationError):
        WeatherWindowInput(district="Sangrur", start_date="bad_date", end_date="bad_date")  # type: ignore[arg-type]


def test_failure_mode_farmer_voice_bad_data() -> None:
    """Farmer Voice failure mode: Invalid farmer ID rejected."""
    with pytest.raises(ValidationError):
        FarmerVoiceInput(farmer_id="bad-uuid", inbound_text="hello")  # type: ignore[arg-type]


def test_failure_mode_pricing_negotiation_bad_data() -> None:
    """Pricing Negotiation failure mode: Negative area rejected."""
    with pytest.raises(ValidationError):
        PricingInput(
            farmer_id=uuid.uuid4(),
            field_id=uuid.uuid4(),
            landholding_class=LandholdingClass.MARGINAL,
            service_type=ServiceType.IN_SITU_SOWING,
            area_acres=-2.5,
        )


def test_failure_mode_mrv_bad_data() -> None:
    """MRV failure mode: Non-positive area rejected."""
    with pytest.raises(ValidationError):
        MrvInput(field_id=uuid.uuid4(), area_acres=0.0)
