"""Comprehensive scenario tests for Orchestrator (supervisor) agent."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from stubbleos.agents.orchestrator.graph import build_orchestrator_graph
from stubbleos.agents.orchestrator.logic import (
    handle_replan_event,
    resolve_conflicts,
)
from stubbleos.agents.orchestrator.schemas import (
    DistrictPlan,
    OrchestratorState,
)
from stubbleos.core.events import (
    InMemoryEventBus,
    ReplanTriggered,
)
from stubbleos.core.ids import SeededUUIDFactory
from stubbleos.core.types import (
    ApprovalStatus,
    LandholdingClass,
    MachineType,
    PlanStatus,
    ReplanReason,
)
from stubbleos.data.models import Approval, Base, Consent, Plan
from stubbleos.data.repositories import (
    ApprovalRepository,
    ConsentRepository,
    PlanRepository,
)
from stubbleos.llm.fake import FakeLLM
from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
)

TABLES = [Plan.__table__, Approval.__table__, Consent.__table__]


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"core": None, "pii": None})
    Base.metadata.create_all(engine, tables=TABLES)
    sm = sessionmaker(engine, expire_on_commit=False)
    with sm() as s:
        yield s
    engine.dispose()


@pytest.fixture
def plan_repo(session: Session) -> PlanRepository:
    return PlanRepository(session)


@pytest.fixture
def approval_repo(session: Session) -> ApprovalRepository:
    return ApprovalRepository(session)


@pytest.fixture
def consent_repo(session: Session) -> ConsentRepository:
    return ConsentRepository(session)


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus(id_factory=SeededUUIDFactory(42))


@pytest.fixture
def test_data() -> tuple[list[JobRequest], list[MachineResource]]:
    jobs = [
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.MARGINAL,
            area_acres=2.0,
            earliest_start_hour=0.0,
            deadline_hour=48.0,
            center_lat=30.25,
            center_lon=75.80,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
        JobRequest(
            field_id=uuid.uuid4(),
            farmer_id=uuid.uuid4(),
            landholding_class=LandholdingClass.SMALL,
            area_acres=3.5,
            earliest_start_hour=0.0,
            deadline_hour=72.0,
            center_lat=30.28,
            center_lon=75.83,
            eligible_machine_types=[MachineType.HAPPY_SEEDER],
        ),
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
    return jobs, machines


@pytest.mark.asyncio
async def test_orchestrator_normal_flow(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    jobs, machines = test_data
    fake_llm = FakeLLM(default="Plan executed cleanly.")

    graph = build_orchestrator_graph(
        llm=fake_llm,
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=MemorySaver(),
    )

    state = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        confidence_threshold=0.50,
    )

    config = {"configurable": {"thread_id": "orch_normal_1"}}
    res = await graph.ainvoke(state, config=config)

    assert res["status"] == "completed"
    plan = res["plan"]
    assert plan is not None
    assert plan.district == "Sangrur"
    assert plan.version == 1
    assert len(plan.assignments) > 0

    # Verify database persistence
    saved_plan = plan_repo.get_by_id(plan.plan_id)
    assert saved_plan is not None
    assert saved_plan.status == PlanStatus.ACTIVE

    # Verify event publication
    plan_events = event_bus.of_type("plan.created")
    assert len(plan_events) >= 1


@pytest.mark.asyncio
async def test_scenario_rain_shock_triggers_replan(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    """Scenario 1: Rain forecast shock accelerates deadlines, versions plan (v1 -> v2), and supersedes v1."""
    jobs, machines = test_data
    graph = build_orchestrator_graph(
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=MemorySaver(),
    )

    # Day 1: Initial plan (v1)
    state_v1 = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        confidence_threshold=0.50,
    )
    res_v1 = await graph.ainvoke(state_v1, config={"configurable": {"thread_id": "thread_rain_1"}})
    plan_v1: DistrictPlan = res_v1["plan"]
    assert plan_v1.version == 1

    # Rain shock event occurs!
    rain_event = ReplanTriggered(
        district="Sangrur",
        reason=ReplanReason.RAIN_FORECAST_CHANGE,
        details={"deadline_compression_hours": "12.0"},
    )

    # Replanning invocation with replan_trigger and previous_plan
    state_v2 = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        replan_trigger=rain_event,
        previous_plan=plan_v1,
        confidence_threshold=0.50,
    )
    res_v2 = await graph.ainvoke(state_v2, config={"configurable": {"thread_id": "thread_rain_2"}})
    plan_v2: DistrictPlan = res_v2["plan"]

    assert plan_v2.version == 2
    assert plan_v2.parent_plan_id == plan_v1.plan_id

    # Verify plan_v1 is marked SUPERSEDED in database
    db_plan_v1 = plan_repo.get_by_id(plan_v1.plan_id)
    assert db_plan_v1 is not None
    assert db_plan_v1.status == PlanStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_scenario_machine_breakdown_replan(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    """Scenario 2: Machine breakdown triggers reassignment and machine removal."""
    jobs, machines = test_data
    broken_machine_id = machines[0].machine_id

    # Add a backup machine so assignments can still be fulfilled
    backup_machine = MachineResource(
        machine_id=uuid.uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.2,
        hourly_cost_inr=850.0,
        current_lat=30.27,
        current_lon=75.81,
        available_from_hour=0.0,
    )
    fleet = [machines[0], backup_machine]

    breakdown_event = ReplanTriggered(
        district="Sangrur",
        reason=ReplanReason.MACHINE_BREAKDOWN,
        details={"machine_id": str(broken_machine_id)},
    )

    graph = build_orchestrator_graph(
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=MemorySaver(),
    )

    state = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=fleet,
        replan_trigger=breakdown_event,
        confidence_threshold=0.50,
    )

    res = await graph.ainvoke(state, config={"configurable": {"thread_id": "thread_breakdown"}})
    plan = res["plan"]
    assert plan is not None

    # Verify no assignment was given to the broken machine
    for a in plan.assignments:
        assert a.machine_id != broken_machine_id
        assert a.machine_id == backup_machine.machine_id


@pytest.mark.asyncio
async def test_scenario_burn_detected_replan(
    test_data: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    """Scenario 3: Stubble burn detected removes burnt field from active jobs."""
    jobs, machines = test_data
    burnt_field_id = jobs[0].field_id

    burn_event = ReplanTriggered(
        district="Sangrur",
        reason=ReplanReason.BURN_DETECTED,
        details={"field_id": str(burnt_field_id)},
    )

    filtered_jobs, _ = handle_replan_event(burn_event, jobs, machines)
    remaining_ids = {j.field_id for j in filtered_jobs}
    assert burnt_field_id not in remaining_ids
    assert len(filtered_jobs) == len(jobs) - 1


def test_conflict_resolution_smallholder_priority(
    test_data: tuple[list[JobRequest], list[MachineResource]],
) -> None:
    """Scenario 4: Resolves competing claims prioritizing marginal/smallholders."""
    jobs, machines = test_data
    winner, tb_log = resolve_conflicts(jobs, machines[0], current_hour=0.0)

    assert winner is not None
    # Marginal farmer has earlier deadline (36h vs 48h) and smallholder status
    assert winner.field_id == jobs[0].field_id
    assert tb_log.winning_job_id == jobs[0].field_id


@pytest.mark.asyncio
async def test_scenario_hitl_low_confidence_interrupt_and_resume(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    """Scenario 5: Low confidence triggers LangGraph interrupt, writes Approval, and resumes upon approval."""
    jobs, machines = test_data
    checkpointer = MemorySaver()

    graph = build_orchestrator_graph(
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=checkpointer,
    )

    state = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        force_interrupt=True,
    )

    config = {"configurable": {"thread_id": "hitl_thread_1"}}

    # Step 1: Invocation halts at interrupt
    interrupted_state = await graph.ainvoke(state, config=config)
    assert "__interrupt__" in interrupted_state
    interrupt_payload = interrupted_state["__interrupt__"][0].value
    assert "approval_id" in interrupt_payload

    approval_id = uuid.UUID(interrupt_payload["approval_id"])

    # Verify pending Approval in database repository
    pending_appr = approval_repo.get_by_id(approval_id)
    assert pending_appr is not None
    assert pending_appr.status == ApprovalStatus.PENDING

    # Verify ApprovalRequested event
    appr_events = event_bus.of_type("approval.requested")
    assert len(appr_events) >= 1

    # Step 2: Coordinator approves and graph resumes
    resumed_state = await graph.ainvoke(
        Command(resume={"status": "approved", "decided_by_role": "fpo_coordinator"}),
        config=config,
    )

    assert resumed_state["status"] == "completed"
    assert resumed_state["plan"] is not None

    # Verify resolved Approval in database
    resolved_appr = approval_repo.get_by_id(approval_id)
    assert resolved_appr is not None
    assert resolved_appr.status == ApprovalStatus.APPROVED

    # Verify ApprovalResolved event
    resolved_events = event_bus.of_type("approval.resolved")
    assert len(resolved_events) >= 1


@pytest.mark.asyncio
async def test_scenario_hitl_rejection(
    test_data: tuple[list[JobRequest], list[MachineResource]],
    plan_repo: PlanRepository,
    approval_repo: ApprovalRepository,
    event_bus: InMemoryEventBus,
) -> None:
    """Scenario 6: Coordinator rejects low-confidence plan; plan is aborted."""
    jobs, machines = test_data
    checkpointer = MemorySaver()

    graph = build_orchestrator_graph(
        plan_repo=plan_repo,
        approval_repo=approval_repo,
        event_bus=event_bus,
        checkpointer=checkpointer,
    )

    state = OrchestratorState(
        district="Sangrur",
        plan_date=date(2026, 10, 20),
        strategy="centralized",
        jobs=jobs,
        machines=machines,
        force_interrupt=True,
    )

    config = {"configurable": {"thread_id": "hitl_thread_reject"}}

    # Step 1: Halts at interrupt
    await graph.ainvoke(state, config=config)

    # Step 2: Coordinator rejects
    resumed_state = await graph.ainvoke(
        Command(resume={"status": "rejected", "decided_by_role": "fpo_coordinator"}),
        config=config,
    )

    assert resumed_state["approval_status"] == ApprovalStatus.REJECTED
    assert resumed_state.get("plan") is None
