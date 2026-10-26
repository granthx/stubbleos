"""Conflict resolution policy with deadline-weighted priority, fairness constraints, and typed tie-break logs."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import LandholdingClass
from stubbleos.optimization.scheduler import JobRequest, MachineResource
from stubbleos.simulation.model import haversine_distance_km


class TieBreakCriterion(StrEnum):
    """Auditable criteria used to resolve competing resource claims."""

    FAIRNESS_SMALLHOLDER_PRIORITY = "fairness_smallholder_priority"
    DEADLINE_URGENCY = "deadline_urgency"
    DISTANCE_PROXIMITY = "distance_proximity"
    DETERMINISTIC_SEED_HASH = "deterministic_seed_hash"


class TieBreakLog(BaseModel):
    """Auditable, typed record of a conflict resolution decision."""

    model_config = ConfigDict(extra="forbid")

    log_id: UUID = Field(default_factory=uuid4)
    resource_id: UUID
    candidate_job_ids: list[UUID]
    criterion_applied: TieBreakCriterion
    winning_job_id: UUID
    reason: str
    timestamp_hour: float


class ConflictResolver:
    """Evaluates competing job claims on a machine resource using deadline and fairness policies."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.audit_log: list[TieBreakLog] = []

    def resolve_competition(
        self,
        jobs: list[JobRequest],
        machine: MachineResource,
        current_hour: float,
    ) -> tuple[JobRequest, TieBreakLog]:
        """Resolves contention among candidate jobs for an available machine."""
        if not jobs:
            raise ValueError("Cannot resolve empty list of competing jobs.")
        if len(jobs) == 1:
            log = TieBreakLog(
                resource_id=machine.machine_id,
                candidate_job_ids=[jobs[0].field_id],
                criterion_applied=TieBreakCriterion.DEADLINE_URGENCY,
                winning_job_id=jobs[0].field_id,
                reason="Single candidate without contention.",
                timestamp_hour=round(current_hour, 2),
            )
            self.audit_log.append(log)
            return jobs[0], log

        job_ids = [j.field_id for j in jobs]

        # 1. Fairness check: Prioritize marginal/small farmers if deadline is near (within 5 days / 120 hrs)
        smallholder_classes = {LandholdingClass.MARGINAL, LandholdingClass.SMALL}
        urgent_smallholders = [
            j
            for j in jobs
            if j.landholding_class in smallholder_classes and (j.deadline_hour - current_hour) <= 120.0
        ]

        active_pool = urgent_smallholders if urgent_smallholders else jobs
        criterion = (
            TieBreakCriterion.FAIRNESS_SMALLHOLDER_PRIORITY
            if urgent_smallholders and len(urgent_smallholders) < len(jobs)
            else TieBreakCriterion.DEADLINE_URGENCY
        )

        # 2. Sort by deadline urgency (earliest deadline first)
        min_deadline = min(j.deadline_hour for j in active_pool)
        tied_urgent = [j for j in active_pool if abs(j.deadline_hour - min_deadline) < 0.5]

        if len(tied_urgent) == 1:
            winner = tied_urgent[0]
            log = TieBreakLog(
                resource_id=machine.machine_id,
                candidate_job_ids=job_ids,
                criterion_applied=criterion,
                winning_job_id=winner.field_id,
                reason=f"Selected due to {criterion.value} (deadline {winner.deadline_hour:.1f}h).",
                timestamp_hour=round(current_hour, 2),
            )
            self.audit_log.append(log)
            return winner, log

        # 3. Distance proximity: closest field to machine
        def get_dist(j: JobRequest) -> float:
            return haversine_distance_km(machine.current_lat, machine.current_lon, j.center_lat, j.center_lon)

        min_dist = min(get_dist(j) for j in tied_urgent)
        tied_proximate = [j for j in tied_urgent if abs(get_dist(j) - min_dist) < 0.2]

        if len(tied_proximate) == 1:
            winner = tied_proximate[0]
            log = TieBreakLog(
                resource_id=machine.machine_id,
                candidate_job_ids=job_ids,
                criterion_applied=TieBreakCriterion.DISTANCE_PROXIMITY,
                winning_job_id=winner.field_id,
                reason=f"Selected due to minimal transit distance ({min_dist:.2f} km).",
                timestamp_hour=round(current_hour, 2),
            )
            self.audit_log.append(log)
            return winner, log

        # 4. Deterministic seed hash tie-break
        def hash_key(j: JobRequest) -> str:
            raw = f"{self.seed}_{machine.machine_id}_{j.field_id}"
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()

        winner = min(tied_proximate, key=hash_key)
        log = TieBreakLog(
            resource_id=machine.machine_id,
            candidate_job_ids=job_ids,
            criterion_applied=TieBreakCriterion.DETERMINISTIC_SEED_HASH,
            winning_job_id=winner.field_id,
            reason="Tie broken deterministically via run seed hash.",
            timestamp_hour=round(current_hour, 2),
        )
        self.audit_log.append(log)
        return winner, log
