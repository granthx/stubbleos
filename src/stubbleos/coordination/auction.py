"""Contract-net auction protocol for decentralized crop residue task allocation."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.coordination.conflicts import ConflictResolver, TieBreakLog
from stubbleos.core.types import LandholdingClass, MachineType
from stubbleos.optimization.scheduler import JobRequest, MachineResource
from stubbleos.simulation.model import haversine_distance_km


class TaskAnnouncement(BaseModel):
    """Call for Proposals (CFP) announced by a farm field requiring residue clearance."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID  # field_id
    farmer_id: UUID
    landholding_class: LandholdingClass
    area_acres: float = Field(..., gt=0.0)
    center_lat: float
    center_lon: float
    earliest_start_hour: float
    deadline_hour: float
    eligible_machine_types: list[MachineType]


class Bid(BaseModel):
    """Proposal submitted by a machine contractor agent."""

    model_config = ConfigDict(extra="forbid")

    bid_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    machine_id: UUID
    machine_type: MachineType
    offered_start_hour: float
    estimated_completion_hour: float
    price_inr: float
    distance_km: float
    score: float = 0.0


class Award(BaseModel):
    """Binding service contract awarded to the winning bidder."""

    model_config = ConfigDict(extra="forbid")

    award_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    winning_bid_id: UUID
    machine_id: UUID
    scheduled_start_hour: float
    scheduled_completion_hour: float
    agreed_price_inr: float
    is_on_time: bool
    tie_break_log: TieBreakLog | None = None


class AuctionRoundResult(BaseModel):
    """Results of a completed decentralized auction round."""

    model_config = ConfigDict(extra="forbid")

    round_number: int
    announcements_count: int
    bids_count: int
    awards: list[Award]
    unawarded_task_ids: list[UUID]


class ContractNetCoordinator:
    """Orchestrates decentralized task announcements, multi-attribute bidding, and award evaluation."""

    def __init__(self, seed: int = 42, transit_speed_kmh: float = 25.0) -> None:
        self.seed = seed
        self.transit_speed_kmh = transit_speed_kmh
        self.resolver = ConflictResolver(seed=seed)
        self.round_counter = 0

    def run_auction_round(
        self,
        tasks: list[TaskAnnouncement],
        machines: list[MachineResource],
        current_hour: float,
    ) -> AuctionRoundResult:
        """Executes a single contract-net auction round across announced tasks and available machines."""
        self.round_counter += 1
        if not tasks or not machines:
            return AuctionRoundResult(
                round_number=self.round_counter,
                announcements_count=len(tasks),
                bids_count=0,
                awards=[],
                unawarded_task_ids=[t.task_id for t in tasks],
            )

        # 1. Collect bids from machine agents
        all_bids: list[Bid] = []
        bids_by_task: dict[UUID, list[Bid]] = {t.task_id: [] for t in tasks}
        bids_by_machine: dict[UUID, list[Bid]] = {m.machine_id: [] for m in machines}

        for t in tasks:
            for m in machines:
                if m.machine_type not in t.eligible_machine_types:
                    continue

                dist = haversine_distance_km(m.current_lat, m.current_lon, t.center_lat, t.center_lon)
                transit_h = max(0.05, dist / self.transit_speed_kmh)
                start_h = max(t.earliest_start_hour, m.available_from_hour + transit_h)
                dur_h = max(0.1, t.area_acres / m.capacity_acres_per_hour)
                comp_h = start_h + dur_h
                cost_inr = dur_h * m.hourly_cost_inr

                # Multi-attribute scoring: higher is better
                # Utility = OnTimeBonus - TransitPenalty - CostPenalty
                is_on_time = comp_h <= t.deadline_hour
                time_slack = max(0.0, t.deadline_hour - comp_h)
                utility = (
                    (1000.0 if is_on_time else -500.0)
                    + (time_slack * 10.0)
                    - (dist * 2.0)
                    - (cost_inr * 0.05)
                )

                bid = Bid(
                    task_id=t.task_id,
                    machine_id=m.machine_id,
                    machine_type=m.machine_type,
                    offered_start_hour=round(start_h, 2),
                    estimated_completion_hour=round(comp_h, 2),
                    price_inr=round(cost_inr, 2),
                    distance_km=round(dist, 2),
                    score=round(utility, 2),
                )
                all_bids.append(bid)
                bids_by_task[t.task_id].append(bid)
                bids_by_machine[m.machine_id].append(bid)

        # 2. Match machines to tasks without double-booking
        # We sort tasks by deadline urgency and smallholder priority
        task_map = {t.task_id: t for t in tasks}
        assigned_machines: set[UUID] = set()
        awards: list[Award] = []
        assigned_tasks: set[UUID] = set()

        # Group contending tasks per machine and resolve conflicts
        for m in machines:
            m_bids = [b for b in bids_by_machine[m.machine_id] if b.task_id not in assigned_tasks]
            if not m_bids:
                continue

            contending_jobs = [
                JobRequest(
                    field_id=b.task_id,
                    farmer_id=task_map[b.task_id].farmer_id,
                    landholding_class=task_map[b.task_id].landholding_class,
                    area_acres=task_map[b.task_id].area_acres,
                    earliest_start_hour=task_map[b.task_id].earliest_start_hour,
                    deadline_hour=task_map[b.task_id].deadline_hour,
                    center_lat=task_map[b.task_id].center_lat,
                    center_lon=task_map[b.task_id].center_lon,
                    eligible_machine_types=[m.machine_type],
                )
                for b in m_bids
            ]

            winner_job, tb_log = self.resolver.resolve_competition(contending_jobs, m, current_hour)
            winning_bid = next(b for b in m_bids if b.task_id == winner_job.field_id)

            awards.append(
                Award(
                    task_id=winner_job.field_id,
                    winning_bid_id=winning_bid.bid_id,
                    machine_id=m.machine_id,
                    scheduled_start_hour=winning_bid.offered_start_hour,
                    scheduled_completion_hour=winning_bid.estimated_completion_hour,
                    agreed_price_inr=winning_bid.price_inr,
                    is_on_time=winning_bid.estimated_completion_hour
                    <= task_map[winner_job.field_id].deadline_hour,
                    tie_break_log=tb_log,
                )
            )
            assigned_machines.add(m.machine_id)
            assigned_tasks.add(winner_job.field_id)

        unawarded = [t.task_id for t in tasks if t.task_id not in assigned_tasks]

        return AuctionRoundResult(
            round_number=self.round_counter,
            announcements_count=len(tasks),
            bids_count=len(all_bids),
            awards=awards,
            unawarded_task_ids=unawarded,
        )
