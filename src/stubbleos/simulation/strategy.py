"""Coordination strategy interface and baseline implementations for the district simulator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import Any
from uuid import UUID

import numpy as np

from stubbleos.core.types import FieldState, MachineStatus
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
    """Stub for StubbleOS Centralized Strategy (OR-Tools / VRP optimization).

    Scheduled for Phase 3.
    """

    def __init__(self) -> None:
        super().__init__(name="stubbleos_centralized")

    def initialize(self, state: DistrictState, rng: np.random.Generator) -> None:
        raise NotImplementedError("StubbleOS Centralized Strategy will be implemented in Phase 3.")

    def on_field_harvested(self, field: SimulatedField, current_day: float) -> SimulatedMachine | None:
        raise NotImplementedError("StubbleOS Centralized Strategy will be implemented in Phase 3.")

    def on_machine_available(self, machine: SimulatedMachine, current_day: float) -> SimulatedField | None:
        raise NotImplementedError("StubbleOS Centralized Strategy will be implemented in Phase 3.")

    def on_day_start(self, day: float) -> list[tuple[SimulatedMachine, SimulatedField]]:
        raise NotImplementedError("StubbleOS Centralized Strategy will be implemented in Phase 3.")

    def has_confirmed_booking(self, field_id: UUID) -> bool:
        raise NotImplementedError("StubbleOS Centralized Strategy will be implemented in Phase 3.")


class StubbleOSDecentralizedStrategy(CoordinationStrategy):
    """Stub for StubbleOS Decentralized Strategy (Multi-Agent Negotiation).

    Scheduled for Phase 3.
    """

    def __init__(self) -> None:
        super().__init__(name="stubbleos_decentralized")

    def initialize(self, state: DistrictState, rng: np.random.Generator) -> None:
        raise NotImplementedError("StubbleOS Decentralized Strategy will be implemented in Phase 3.")

    def on_field_harvested(self, field: SimulatedField, current_day: float) -> SimulatedMachine | None:
        raise NotImplementedError("StubbleOS Decentralized Strategy will be implemented in Phase 3.")

    def on_machine_available(self, machine: SimulatedMachine, current_day: float) -> SimulatedField | None:
        raise NotImplementedError("StubbleOS Decentralized Strategy will be implemented in Phase 3.")

    def on_day_start(self, day: float) -> list[tuple[SimulatedMachine, SimulatedField]]:
        raise NotImplementedError("StubbleOS Decentralized Strategy will be implemented in Phase 3.")

    def has_confirmed_booking(self, field_id: UUID) -> bool:
        raise NotImplementedError("StubbleOS Decentralized Strategy will be implemented in Phase 3.")
