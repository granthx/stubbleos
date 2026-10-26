"""Coordination strategy interface and baseline implementations for the district simulator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import Any
from uuid import UUID

import numpy as np

from stubbleos.core.types import FieldState, MachineStatus, MachineType
from stubbleos.simulation.model import (
    DistrictState,
    SimulatedField,
    SimulatedMachine,
    haversine_distance_km,
)


class CoordinationStrategy(ABC):
    """Abstract interface for crop residue management coordination strategies."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.state: DistrictState | None = None
        self.rng: np.random.Generator | None = None
        self.messages_count: int = 0
        self.llm_calls_count: int = 0
        self.total_planning_latency_ms: float = 0.0

    def initialize(self, state: DistrictState, rng: np.random.Generator) -> None:
        """Initialize the strategy with district state and deterministic RNG."""
        self.state = state
        self.rng = rng
        self.messages_count = 0
        self.llm_calls_count = 0
        self.total_planning_latency_ms = 0.0

    @abstractmethod
    def on_field_harvested(self, field: SimulatedField, current_day: float) -> SimulatedMachine | None:
        """Invoked when a field completes harvesting and residue becomes present.

        Returns an assigned machine if immediate dispatch occurs, else None.
        """
        ...

    @abstractmethod
    def on_machine_available(self, machine: SimulatedMachine, current_day: float) -> SimulatedField | None:
        """Invoked when a machine becomes free (idle or finished with prior task).

        Returns the next field to service if assigned, else None.
        """
        ...

    @abstractmethod
    def on_day_start(self, day: float) -> list[tuple[SimulatedMachine, SimulatedField]]:
        """Invoked at the beginning of each simulated day for periodic matching or retries.

        Returns list of (machine, field) assignments made.
        """
        ...

    @abstractmethod
    def has_confirmed_booking(self, field_id: UUID) -> bool:
        """Returns True if the field has a confirmed active booking or queue position."""
        ...

    def get_overhead_metrics(self) -> dict[str, Any]:
        """Return coordination overhead metrics (messages, LLM calls, latency)."""
        return {
            "messages_count": self.messages_count,
            "llm_calls_count": self.llm_calls_count,
            "total_planning_latency_ms": round(self.total_planning_latency_ms, 2),
        }


class BaselineAStrategy(CoordinationStrategy):
    """Baseline A: No coordination.

    Farmers act independently with fixed probabilities of seeking machines vs burning.
    Farmers search locally (within a search radius) directly for idle machines.
    There is no central queue; if no machine is found immediately, the request fails.
    Farmers may re-check each morning, but urgency/trust decay drives burning on deadline.
    """

    def __init__(self, search_radius_km: float = 12.0, p_seek_machine: float = 0.75) -> None:
        super().__init__(name="baseline_a")
        self.search_radius_km = search_radius_km
        self.p_seek_machine = p_seek_machine
        self.active_bookings: set[UUID] = set()

    def on_field_harvested(self, field: SimulatedField, current_day: float) -> SimulatedMachine | None:
        if self.state is None or self.rng is None:
            return None

        # Fixed probability of seeking a machine vs immediate burn intent
        if self.rng.random() > self.p_seek_machine:
            return None

        # Farmer searches locally for an available machine within radius
        best_machine: SimulatedMachine | None = None
        best_dist = float("inf")

        for m in self.state.machines:
            if m.status == MachineStatus.AVAILABLE and m.current_field_id is None:
                dist = haversine_distance_km(field.center_lat, field.center_lon, m.current_lat, m.current_lon)
                if dist <= self.search_radius_km and dist < best_dist:
                    best_dist = dist
                    best_machine = m

        if best_machine is not None:
            self.active_bookings.add(field.field_id)
            return best_machine

        return None

    def on_machine_available(self, machine: SimulatedMachine, current_day: float) -> SimulatedField | None:
        if self.state is None:
            return None
        # In Baseline A, machines sit idle until a local farmer directly calls/engages them
        return None

    def on_day_start(self, day: float) -> list[tuple[SimulatedMachine, SimulatedField]]:
        """Unserved farmers with pending residue make another local phone check in the morning."""
        if self.state is None or self.rng is None:
            return []

        assignments: list[tuple[SimulatedMachine, SimulatedField]] = []
        pending_fields = [
            f
            for f in self.state.fields
            if f.state == FieldState.HARVESTED_RESIDUE_PRESENT
            and not f.service_in_progress
            and f.field_id not in self.active_bookings
        ]

        # Randomize farmer check order (farmers call independently)
        self.rng.shuffle(pending_fields)

        for field in pending_fields:
            if self.rng.random() > self.p_seek_machine:
                continue

            best_machine: SimulatedMachine | None = None
            best_dist = float("inf")

            for m in self.state.machines:
                if m.status == MachineStatus.AVAILABLE and m.current_field_id is None:
                    dist = haversine_distance_km(
                        field.center_lat, field.center_lon, m.current_lat, m.current_lon
                    )
                    if dist <= self.search_radius_km and dist < best_dist:
                        best_dist = dist
                        best_machine = m

            if best_machine is not None:
                best_machine.status = MachineStatus.IN_USE
                best_machine.current_field_id = field.field_id
                self.active_bookings.add(field.field_id)
                assignments.append((best_machine, field))

        return assignments

    def has_confirmed_booking(self, field_id: UUID) -> bool:
        return field_id in self.active_bookings


class BaselineBStrategy(CoordinationStrategy):
    """Baseline B: First-Come-First-Served (FCFS) machine allocation.

    Farmers submit requests to a centralized queue upon harvest.
    Available machines are dispatched to the earliest queued request that has not burned.
    Farmers with queued requests know they have a booking, reducing panic burns.
    """

    def __init__(self) -> None:
        super().__init__(name="baseline_b")
        self.queue: deque[UUID] = deque()
        self.queued_set: set[UUID] = set()

    def initialize(self, state: DistrictState, rng: np.random.Generator) -> None:
        super().initialize(state, rng)
        self.queue.clear()
        self.queued_set.clear()

    def on_field_harvested(self, field: SimulatedField, current_day: float) -> SimulatedMachine | None:
        if self.state is None:
            return None

        # Record booking request message
        self.messages_count += 1
        self.total_planning_latency_ms += 0.05

        if field.field_id not in self.queued_set:
            self.queue.append(field.field_id)
            self.queued_set.add(field.field_id)

        # Check if any machine is currently idle
        for m in self.state.machines:
            if m.status == MachineStatus.AVAILABLE and m.current_field_id is None:
                # Dispatch immediately to this field if it is at front of queue
                if self.queue and self.queue[0] == field.field_id:
                    self.queue.popleft()
                    self.messages_count += 1  # Dispatch notification message
                    return m
                # Otherwise let the normal queue order prevail
                break

        return None

    def on_machine_available(self, machine: SimulatedMachine, current_day: float) -> SimulatedField | None:
        if self.state is None:
            return None

        # Pop from queue until we find a field that is still valid (not burned or cleared)
        while self.queue:
            next_field_id = self.queue.popleft()
            field = self.state.get_field(next_field_id)
            if field.state == FieldState.HARVESTED_RESIDUE_PRESENT and not field.service_in_progress:
                self.messages_count += 1  # Dispatch notification
                self.total_planning_latency_ms += 0.05
                return field

        return None

    def on_day_start(self, day: float) -> list[tuple[SimulatedMachine, SimulatedField]]:
        """Dispatch any idle machines to pending queued fields."""
        if self.state is None:
            return []

        assignments: list[tuple[SimulatedMachine, SimulatedField]] = []
        for m in self.state.machines:
            if m.status == MachineStatus.AVAILABLE and m.current_field_id is None:
                field = self.on_machine_available(m, day)
                if field is not None:
                    m.status = MachineStatus.IN_USE
                    m.current_field_id = field.field_id
                    assignments.append((m, field))

        return assignments

    def has_confirmed_booking(self, field_id: UUID) -> bool:
        return field_id in self.queued_set


class StubbleOSCentralizedStrategy(CoordinationStrategy):
    """StubbleOS Centralized Strategy: CP-SAT optimization with VRP logistics.

    Periodically solves a global multi-machine scheduling model (CP-SAT) with
    deadline-weighted coverage and smallholder fairness weighting.
    """

    def __init__(self, time_limit_seconds: float = 0.05) -> None:
        super().__init__(name="stubbleos_centralized")
        self.time_limit_seconds = time_limit_seconds
        self.machine_queues: dict[UUID, deque[UUID]] = {}
        self.confirmed_bookings: set[UUID] = set()

    def initialize(self, state: DistrictState, rng: np.random.Generator) -> None:
        super().initialize(state, rng)
        self.machine_queues = {m.machine_id: deque() for m in state.machines}
        self.confirmed_bookings.clear()

    def on_field_harvested(self, field: SimulatedField, current_day: float) -> SimulatedMachine | None:
        # Field registers with central system
        self.messages_count += 1
        self.confirmed_bookings.add(field.field_id)

        # Check if an immediate machine of suitable type is idle
        if self.state is not None:
            for m in self.state.machines:
                if (
                    m.status == MachineStatus.AVAILABLE
                    and m.current_field_id is None
                    and not self.machine_queues[m.machine_id]
                ):
                    self.messages_count += 1
                    return m
        return None

    def on_machine_available(self, machine: SimulatedMachine, current_day: float) -> SimulatedField | None:
        if self.state is None:
            return None

        # Check pre-computed queue for this machine
        q = self.machine_queues.get(machine.machine_id, deque())
        while q:
            f_id = q.popleft()
            f = self.state.get_field(f_id)
            if f.state == FieldState.HARVESTED_RESIDUE_PRESENT and not f.service_in_progress:
                self.messages_count += 1
                return f

        # If machine queue empty, look for any unassigned pending field
        for f in self.state.fields:
            if (
                f.state == FieldState.HARVESTED_RESIDUE_PRESENT
                and not f.service_in_progress
                and f.field_id not in self.confirmed_bookings
            ):
                self.confirmed_bookings.add(f.field_id)
                self.messages_count += 1
                return f

        return None

    def on_day_start(self, day: float) -> list[tuple[SimulatedMachine, SimulatedField]]:
        """Run CP-SAT solver on pending residue fields when idle machines are available."""
        if self.state is None or self.rng is None:
            return []

        # Collect pending unserviced fields
        pending_fields = [
            f
            for f in self.state.fields
            if f.state == FieldState.HARVESTED_RESIDUE_PRESENT and not f.service_in_progress
        ]

        if not pending_fields:
            return []

        idle_machines = [
            m
            for m in self.state.machines
            if m.status == MachineStatus.AVAILABLE and m.current_field_id is None
        ]

        unassigned_pending = [
            f for f in pending_fields if not any(f.field_id in q for q in self.machine_queues.values())
        ]

        # Only solve CP-SAT if there are both idle machines and unassigned pending fields
        if not idle_machines or not unassigned_pending:
            assignments: list[tuple[SimulatedMachine, SimulatedField]] = []
            for m in idle_machines:
                field = self.on_machine_available(m, day)
                if field is not None:
                    m.status = MachineStatus.IN_USE
                    m.current_field_id = field.field_id
                    assignments.append((m, field))
            return assignments

        from stubbleos.optimization.scheduler import (
            JobRequest,
            MachineResource,
            SchedulerConfig,
        )

        current_hour = day * 24.0
        jobs: list[JobRequest] = []
        for f in unassigned_pending[:40]:  # batch up to 40 fields per solve
            farmer = self.state.get_farmer(f.farmer_id)
            jobs.append(
                JobRequest(
                    field_id=f.field_id,
                    farmer_id=f.farmer_id,
                    landholding_class=farmer.landholding_class,
                    area_acres=f.area_acres,
                    earliest_start_hour=max(current_hour, f.harvest_day * 24.0),
                    deadline_hour=f.sowing_deadline_day * 24.0,
                    center_lat=f.center_lat,
                    center_lon=f.center_lon,
                    eligible_machine_types=list(MachineType),
                )
            )

        machines = [
            MachineResource(
                machine_id=m.machine_id,
                machine_type=m.machine_type,
                capacity_acres_per_hour=m.capacity_acres_per_hour,
                hourly_cost_inr=m.hourly_cost_inr,
                current_lat=m.current_lat,
                current_lon=m.current_lon,
                available_from_hour=current_hour,
            )
            for m in self.state.machines
        ]

        seed_int = int(self.rng.integers(1, 100000))
        cfg = SchedulerConfig(
            time_limit_seconds=self.time_limit_seconds,
            random_seed=seed_int,
        )

        import asyncio

        from stubbleos.agents.machine_scheduler.logic import run_machine_scheduler
        from stubbleos.agents.machine_scheduler.schemas import MachineSchedulerInput
        from stubbleos.agents.policy_guard.logic import evaluate_policy
        from stubbleos.agents.policy_guard.schemas import PolicyCheckRequest
        from stubbleos.llm.fake import FakeLLM

        agent_inp = MachineSchedulerInput(
            jobs=jobs,
            machines=machines,
            mode="cpsat",
            config=cfg,
            request_explanation=True,
        )
        fake_llm = FakeLLM(default="Centralized CP-SAT schedule computed successfully.")
        output = asyncio.run(run_machine_scheduler(agent_inp, llm=fake_llm))
        self.llm_calls_count += 1
        self.total_planning_latency_ms += output.wall_time_seconds * 1000.0

        # Run cross-cutting Policy Guard validation on planned assignments
        policy_req = PolicyCheckRequest(
            action_ref=f"dispatch_day_{day:.0f}",
            payload={"assigned_count": len(output.assignments)},
        )
        policy_res = evaluate_policy(policy_req)
        if not policy_res.is_allowed:
            return []

        # Update confirmed bookings and queues
        for a in output.assignments:
            self.confirmed_bookings.add(a.field_id)
            if a.field_id not in self.machine_queues[a.machine_id]:
                self.machine_queues[a.machine_id].append(a.field_id)

        self.messages_count += len(output.assignments) * 2

        # Dispatch idle machines immediately
        dispatched_assignments: list[tuple[SimulatedMachine, SimulatedField]] = []
        for m in self.state.machines:
            if m.status == MachineStatus.AVAILABLE and m.current_field_id is None:
                field = self.on_machine_available(m, day)
                if field is not None:
                    m.status = MachineStatus.IN_USE
                    m.current_field_id = field.field_id
                    dispatched_assignments.append((m, field))

        return dispatched_assignments

    def has_confirmed_booking(self, field_id: UUID) -> bool:
        return field_id in self.confirmed_bookings


class StubbleOSDecentralizedStrategy(CoordinationStrategy):
    """StubbleOS Decentralized Strategy: Contract-Net Protocol (CNP) auctions.

    Fields broadcast task announcements (CFPs); machines bid based on
    marginal transit and time availability; conflicts are resolved with
    smallholder fairness protection and deterministic tie-breaking.
    """

    def __init__(self) -> None:
        super().__init__(name="stubbleos_decentralized")
        self.coordinator: Any = None
        self.active_awards: dict[UUID, UUID] = {}  # field_id -> machine_id
        self.pending_tasks: dict[UUID, SimulatedField] = {}

    def initialize(self, state: DistrictState, rng: np.random.Generator) -> None:
        super().initialize(state, rng)
        from stubbleos.coordination.auction import ContractNetCoordinator

        seed_int = int(rng.integers(1, 100000))
        self.coordinator = ContractNetCoordinator(seed=seed_int)
        self.active_awards.clear()
        self.pending_tasks.clear()

    def on_field_harvested(self, field: SimulatedField, current_day: float) -> SimulatedMachine | None:
        if self.state is None or self.coordinator is None:
            return None

        self.pending_tasks[field.field_id] = field

        # Check for idle machines to run immediate contract-net auction
        idle_machines = [
            m
            for m in self.state.machines
            if m.status == MachineStatus.AVAILABLE and m.current_field_id is None
        ]

        if not idle_machines:
            return None

        import asyncio

        from stubbleos.agents.machine_scheduler.logic import run_machine_scheduler
        from stubbleos.agents.machine_scheduler.schemas import MachineSchedulerInput
        from stubbleos.agents.policy_guard.logic import evaluate_policy
        from stubbleos.agents.policy_guard.schemas import PolicyCheckRequest
        from stubbleos.optimization.scheduler import JobRequest, MachineResource

        farmer = self.state.get_farmer(field.farmer_id)
        job = JobRequest(
            field_id=field.field_id,
            farmer_id=field.farmer_id,
            landholding_class=farmer.landholding_class,
            area_acres=field.area_acres,
            center_lat=field.center_lat,
            center_lon=field.center_lon,
            earliest_start_hour=field.harvest_day * 24.0,
            deadline_hour=field.sowing_deadline_day * 24.0,
            eligible_machine_types=list(MachineType),
        )

        m_resources = [
            MachineResource(
                machine_id=m.machine_id,
                machine_type=m.machine_type,
                capacity_acres_per_hour=m.capacity_acres_per_hour,
                hourly_cost_inr=m.hourly_cost_inr,
                current_lat=m.current_lat,
                current_lon=m.current_lon,
                available_from_hour=current_day * 24.0,
            )
            for m in idle_machines
        ]

        seed_int = int(self.rng.integers(1, 100000)) if self.rng is not None else 42
        agent_inp = MachineSchedulerInput(
            jobs=[job],
            machines=m_resources,
            mode="auction",
            seed=seed_int,
            current_hour=current_day * 24.0,
            request_explanation=False,
        )
        sched_out = asyncio.run(run_machine_scheduler(agent_inp))
        self.messages_count += len(idle_machines) * 2 + len(sched_out.assignments)
        self.total_planning_latency_ms += 0.5

        if sched_out.assignments:
            award = sched_out.assignments[0]
            policy_req = PolicyCheckRequest(
                action_ref=f"auction_award_{award.field_id}",
                payload={"field_id": str(award.field_id), "machine_id": str(award.machine_id)},
            )
            if evaluate_policy(policy_req).is_allowed:
                self.active_awards[field.field_id] = award.machine_id
                self.pending_tasks.pop(field.field_id, None)
                return self.state.get_machine(award.machine_id)

        return None

    def on_machine_available(self, machine: SimulatedMachine, current_day: float) -> SimulatedField | None:
        if self.state is None or self.coordinator is None:
            return None

        # When machine is freed, auction available pending fields to this machine
        pending = [
            f
            for f in self.state.fields
            if f.state == FieldState.HARVESTED_RESIDUE_PRESENT
            and not f.service_in_progress
            and f.field_id not in self.active_awards
        ]

        if not pending:
            return None

        import asyncio

        from stubbleos.agents.machine_scheduler.logic import run_machine_scheduler
        from stubbleos.agents.machine_scheduler.schemas import MachineSchedulerInput
        from stubbleos.agents.policy_guard.logic import evaluate_policy
        from stubbleos.agents.policy_guard.schemas import PolicyCheckRequest
        from stubbleos.optimization.scheduler import JobRequest, MachineResource

        jobs = []
        for f in pending[:20]:  # Evaluate up to 20 candidate fields in local auction
            farmer = self.state.get_farmer(f.farmer_id)
            jobs.append(
                JobRequest(
                    field_id=f.field_id,
                    farmer_id=f.farmer_id,
                    landholding_class=farmer.landholding_class,
                    area_acres=f.area_acres,
                    center_lat=f.center_lat,
                    center_lon=f.center_lon,
                    earliest_start_hour=f.harvest_day * 24.0,
                    deadline_hour=f.sowing_deadline_day * 24.0,
                    eligible_machine_types=[machine.machine_type],
                )
            )

        m_res = MachineResource(
            machine_id=machine.machine_id,
            machine_type=machine.machine_type,
            capacity_acres_per_hour=machine.capacity_acres_per_hour,
            hourly_cost_inr=machine.hourly_cost_inr,
            current_lat=machine.current_lat,
            current_lon=machine.current_lon,
            available_from_hour=current_day * 24.0,
        )

        seed_int = int(self.rng.integers(1, 100000)) if self.rng is not None else 42
        inp = MachineSchedulerInput(
            jobs=jobs,
            machines=[m_res],
            mode="auction",
            seed=seed_int,
            current_hour=current_day * 24.0,
            request_explanation=False,
        )
        sched_out = asyncio.run(run_machine_scheduler(inp))
        self.messages_count += len(jobs) * 2 + len(sched_out.assignments)
        self.total_planning_latency_ms += 0.5

        if sched_out.assignments:
            award = sched_out.assignments[0]
            policy_req = PolicyCheckRequest(
                action_ref=f"auction_award_{award.field_id}",
                payload={"field_id": str(award.field_id), "machine_id": str(machine.machine_id)},
            )
            if evaluate_policy(policy_req).is_allowed:
                self.active_awards[award.field_id] = machine.machine_id
                return self.state.get_field(award.field_id)

        return None

    def on_day_start(self, day: float) -> list[tuple[SimulatedMachine, SimulatedField]]:
        """Run morning auction round for any unassigned fields and idle machines."""
        if self.state is None:
            return []

        assignments: list[tuple[SimulatedMachine, SimulatedField]] = []
        for m in self.state.machines:
            if m.status == MachineStatus.AVAILABLE and m.current_field_id is None:
                field = self.on_machine_available(m, day)
                if field is not None:
                    m.status = MachineStatus.IN_USE
                    m.current_field_id = field.field_id
                    assignments.append((m, field))

        return assignments

    def has_confirmed_booking(self, field_id: UUID) -> bool:
        return field_id in self.active_awards
