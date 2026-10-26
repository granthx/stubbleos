"""Unit tests for contract-net auctions and conflict resolution policy."""

from uuid import uuid4

import pytest

from stubbleos.coordination.auction import ContractNetCoordinator, TaskAnnouncement
from stubbleos.coordination.conflicts import ConflictResolver, TieBreakCriterion
from stubbleos.core.types import LandholdingClass, MachineType
from stubbleos.optimization.scheduler import JobRequest, MachineResource


def test_contract_net_auction_flow() -> None:
    coord = ContractNetCoordinator(seed=42)

    task = TaskAnnouncement(
        task_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SMALL,
        area_acres=4.0,
        center_lat=30.8,
        center_lon=75.8,
        earliest_start_hour=0.0,
        deadline_hour=24.0,
        eligible_machine_types=[MachineType.HAPPY_SEEDER],
    )

    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.2,
        hourly_cost_inr=1800.0,
        current_lat=30.81,
        current_lon=75.81,
        available_from_hour=0.0,
    )

    result = coord.run_auction_round(tasks=[task], machines=[machine], current_hour=0.0)

    assert result.round_number == 1
    assert result.announcements_count == 1
    assert result.bids_count == 1
    assert len(result.awards) == 1

    award = result.awards[0]
    assert award.task_id == task.task_id
    assert award.machine_id == machine.machine_id
    assert award.is_on_time is True
    assert award.agreed_price_inr > 0.0


def test_conflict_resolution_smallholder_priority() -> None:
    resolver = ConflictResolver(seed=100)
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.SUPER_SEEDER,
        capacity_acres_per_hour=1.5,
        hourly_cost_inr=2000.0,
        current_lat=30.8,
        current_lon=75.8,
    )

    small_job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.MARGINAL,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=48.0,  # Urgent smallholder
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )
    large_job = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.LARGE,
        area_acres=3.0,
        earliest_start_hour=0.0,
        deadline_hour=48.0,
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.SUPER_SEEDER],
    )

    winner, log = resolver.resolve_competition([small_job, large_job], machine, current_hour=0.0)
    assert winner.field_id == small_job.field_id
    assert log.criterion_applied == TieBreakCriterion.FAIRNESS_SMALLHOLDER_PRIORITY
    assert log.winning_job_id == small_job.field_id
    assert len(resolver.audit_log) == 1


def test_conflict_resolution_deadline_urgency_and_tie_breaking() -> None:
    resolver = ConflictResolver(seed=42)
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.BALER,
        capacity_acres_per_hour=2.0,
        hourly_cost_inr=2400.0,
        current_lat=30.8,
        current_lon=75.8,
    )

    job_urgent = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,  # More urgent
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.BALER],
    )
    job_relaxed = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=60.0,  # Less urgent
        center_lat=30.8,
        center_lon=75.8,
        eligible_machine_types=[MachineType.BALER],
    )

    winner, log = resolver.resolve_competition([job_urgent, job_relaxed], machine, current_hour=0.0)
    assert winner.field_id == job_urgent.field_id
    assert log.criterion_applied == TieBreakCriterion.DEADLINE_URGENCY


def test_conflict_resolution_distance_and_deterministic_hash() -> None:
    resolver = ConflictResolver(seed=42)
    machine = MachineResource(
        machine_id=uuid4(),
        machine_type=MachineType.BALER,
        capacity_acres_per_hour=2.0,
        hourly_cost_inr=2400.0,
        current_lat=30.8,
        current_lon=75.8,
    )

    # 1. Distance proximity test
    job_near = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.81,  # near (~1.1 km)
        center_lon=75.81,
        eligible_machine_types=[MachineType.BALER],
    )
    job_far = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.95,  # far (>15 km)
        center_lon=75.95,
        eligible_machine_types=[MachineType.BALER],
    )
    winner_dist, log_dist = resolver.resolve_competition([job_near, job_far], machine, current_hour=0.0)
    assert winner_dist.field_id == job_near.field_id
    assert log_dist.criterion_applied == TieBreakCriterion.DISTANCE_PROXIMITY

    # 2. Deterministic hash tie-break test (identical lat, lon, deadline, class)
    job_tie_1 = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.81,
        center_lon=75.81,
        eligible_machine_types=[MachineType.BALER],
    )
    job_tie_2 = JobRequest(
        field_id=uuid4(),
        farmer_id=uuid4(),
        landholding_class=LandholdingClass.SEMI_MEDIUM,
        area_acres=5.0,
        earliest_start_hour=0.0,
        deadline_hour=20.0,
        center_lat=30.81,
        center_lon=75.81,
        eligible_machine_types=[MachineType.BALER],
    )
    winner_hash, log_hash = resolver.resolve_competition([job_tie_1, job_tie_2], machine, current_hour=0.0)
    assert winner_hash.field_id in (job_tie_1.field_id, job_tie_2.field_id)
    assert log_hash.criterion_applied == TieBreakCriterion.DETERMINISTIC_SEED_HASH

    # 3. Single candidate job
    winner_single, _log_single = resolver.resolve_competition([job_near], machine, current_hour=0.0)
    assert winner_single.field_id == job_near.field_id

    # 4. Empty candidate job list raises ValueError
    with pytest.raises(ValueError, match="Cannot resolve empty list"):
        resolver.resolve_competition([], machine, current_hour=0.0)
