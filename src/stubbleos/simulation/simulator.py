"""SimPy-based reproducible discrete-event district simulator."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import numpy as np
import simpy

from stubbleos.core.clock import SimClock
from stubbleos.core.types import FieldState, MachineStatus, MachineType
from stubbleos.simulation.config import ScenarioConfig
from stubbleos.simulation.generator import generate_synthetic_district
from stubbleos.simulation.model import (
    DistrictState,
    SimulatedBuyer,
    SimulatedField,
    SimulatedMachine,
    SimulatedTruck,
    haversine_distance_km,
)
from stubbleos.simulation.stochastic import (
    RainSchedule,
    generate_rain_schedule,
    sample_machine_breakdown,
    should_farmer_burn,
)
from stubbleos.simulation.strategy import CoordinationStrategy


class DistrictSimulator:
    """Simulates a farming district over a paddy harvesting season using SimPy.

    All stochastic behavior flows strictly from one seed via NumPy Generator.
    Guarantees byte-identical reproduction for identical (config, seed) pairs.
    """

    def __init__(
        self,
        config: ScenarioConfig,
        strategy: CoordinationStrategy,
        seed: int,
    ) -> None:
        self.config = config
        self.strategy = strategy
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Generate synthetic district state and initialize deterministic clock
        self.state: DistrictState = generate_synthetic_district(config, seed)
        self.clock = SimClock(config.season_start)
        self.rain_schedule: RainSchedule = generate_rain_schedule(config, self.rng)

        # Setup SimPy environment (env.now measured in hours)
        self.env = simpy.Environment()
        self.total_season_hours = float(config.season_length_days * 24)

        # Active machine job processes tracking to prevent concurrent dispatch
        self._busy_machines: set[UUID] = set()
        self._servicing_fields: set[UUID] = set()

    def run(self) -> DistrictState:
        """Execute the simulation run to completion and return final district state."""
        self.strategy.initialize(self.state, self.rng)

        # Register top-level SimPy processes
        self.env.process(self._harvest_scheduler_process())
        self.env.process(self._daily_management_process())

        # Run SimPy simulation until season ends
        self.env.run(until=self.total_season_hours)

        # Finalize accounting at season end
        self._finalize_simulation()
        return self.state

    def _harvest_scheduler_process(self) -> simpy.events.ProcessGenerator:
        """Releases fields for residue management at their respective harvest times."""
        # Sort fields chronologically by harvest day
        sorted_fields = sorted(self.state.fields, key=lambda f: f.harvest_day)

        for field in sorted_fields:
            harvest_hour = field.harvest_day * 24.0
            if harvest_hour > self.env.now:
                yield self.env.timeout(harvest_hour - self.env.now)

            # Field matures to harvested residue state
            field.state = FieldState.HARVESTED_RESIDUE_PRESENT
            current_day = self.env.now / 24.0

            # Notify strategy
            assigned_machine = self.strategy.on_field_harvested(field, current_day)
            if assigned_machine is not None and assigned_machine.machine_id not in self._busy_machines:
                self.env.process(self._machine_job_process(assigned_machine, field))

    def _daily_management_process(self) -> simpy.events.ProcessGenerator:
        """Evaluates daily farmer burn urgency and periodic machine matching."""
        # Run daily check every morning at 08:00 (hours 8, 32, 56, ...)
        yield self.env.timeout(8.0)

        while self.env.now < self.total_season_hours:
            current_day = self.env.now / 24.0
            # Advance deterministic clock
            self.clock.set(self.config.season_start + timedelta(hours=self.env.now))

            # 1. Strategy daily matching
            assignments = self.strategy.on_day_start(current_day)
            for machine, field in assignments:
                if (
                    machine.machine_id not in self._busy_machines
                    and field.field_id not in self._servicing_fields
                ):
                    self.env.process(self._machine_job_process(machine, field))

            # 2. Daily farmer burn evaluation for pending fields
            for field in self.state.fields:
                if (
                    field.state == FieldState.HARVESTED_RESIDUE_PRESENT
                    and not field.service_in_progress
                    and field.field_id not in self._servicing_fields
                ):
                    farmer = self.state.get_farmer(field.farmer_id)
                    has_booking = self.strategy.has_confirmed_booking(field.field_id)

                    if should_farmer_burn(farmer, field, current_day, has_booking, self.rng):
                        field.state = FieldState.BURN_DETECTED
                        field.burned_at_day = round(current_day, 2)
                        # Farmer suffers regulatory fine / soil loss penalty (synthetic: 1500 INR/acre)
                        farmer.burn_cost_penalty_inr += round(1500.0 * field.area_acres, 2)

            # Wait 24 hours until next morning's evaluation
            yield self.env.timeout(24.0)

    def _machine_job_process(
        self, machine: SimulatedMachine, field: SimulatedField
    ) -> simpy.events.ProcessGenerator:
        """Simulates transit, breakdown, and execution of machine service on a field."""
        if machine.machine_id in self._busy_machines or field.field_id in self._servicing_fields:
            return

        self._busy_machines.add(machine.machine_id)
        self._servicing_fields.add(field.field_id)

        machine.status = MachineStatus.IN_USE
        machine.current_field_id = field.field_id
        field.assigned_machine_id = machine.machine_id

        try:
            # Check if field was burned before machine dispatch started
            if field.state != FieldState.HARVESTED_RESIDUE_PRESENT:
                return

            # 1. Transit to field
            dist_km = haversine_distance_km(
                machine.current_lat, machine.current_lon, field.center_lat, field.center_lon
            )
            # Transit speed ~25 km/h for agricultural tractors
            transit_hours = max(0.05, dist_km / 25.0)
            yield self.env.timeout(transit_hours)

            machine.transit_hours += transit_hours
            machine.current_lat = field.center_lat
            machine.current_lon = field.center_lon

            # Check if field was burned while machine was in transit
            if field.state != FieldState.HARVESTED_RESIDUE_PRESENT:
                return

            # 2. Weather check: wait if raining
            current_day = self.env.now / 24.0
            if self.rain_schedule.is_raining(current_day):
                rain_event = self.rain_schedule.next_rain_event(current_day)
                if rain_event is not None:
                    rain_wait_hours = max(1.0, rain_event[1] * 24.0 - self.env.now)
                    yield self.env.timeout(rain_wait_hours)

            # Check if field burned during rain wait
            if field.state != FieldState.HARVESTED_RESIDUE_PRESENT:
                return

            # 3. Machine operation
            field.service_in_progress = True
            operating_hours = field.area_acres / machine.capacity_acres_per_hour

            # Check stochastic breakdown
            breakdown_hours = sample_machine_breakdown(machine, operating_hours, self.config, self.rng)
            if breakdown_hours is not None:
                machine.status = MachineStatus.MAINTENANCE
                machine.breakdown_hours += breakdown_hours
                yield self.env.timeout(breakdown_hours)
                machine.status = MachineStatus.IN_USE

            # Execute field operation
            yield self.env.timeout(operating_hours)

            machine.operating_hours += operating_hours
            machine.acres_worked += field.area_acres

            # Farmer pays machine fee
            fee = operating_hours * machine.hourly_cost_inr
            farmer = self.state.get_farmer(field.farmer_id)
            farmer.machine_fees_paid_inr += round(fee, 2)

            # Field cleared successfully!
            field.service_in_progress = False
            field.state = FieldState.CLEARED
            field.cleared_at_day = round(self.env.now / 24.0, 2)

            # 4. If Baler, dispatch straw logistics
            if machine.machine_type in (MachineType.BALER, MachineType.RAKE):
                self._dispatch_straw_logistics(field)

        finally:
            self._busy_machines.discard(machine.machine_id)
            self._servicing_fields.discard(field.field_id)
            machine.status = MachineStatus.AVAILABLE
            machine.current_field_id = None
            field.assigned_machine_id = None

            # Check strategy for immediate next assignment
            next_field = self.strategy.on_machine_available(machine, self.env.now / 24.0)
            if next_field is not None and next_field.field_id not in self._servicing_fields:
                self.env.process(self._machine_job_process(machine, next_field))

    def _dispatch_straw_logistics(self, field: SimulatedField) -> None:
        """Finds nearest buyer with unmet demand and available truck to transport straw."""
        # Find nearest buyer with remaining demand
        best_buyer: SimulatedBuyer | None = None
        min_buyer_dist = float("inf")

        for b in self.state.buyers:
            if b.remaining_demand > 0:
                d = haversine_distance_km(field.center_lat, field.center_lon, b.lat, b.lon)
                if d < min_buyer_dist:
                    min_buyer_dist = d
                    best_buyer = b

        if best_buyer is None:
            return

        # Find available truck
        available_truck: SimulatedTruck | None = None
        for t in self.state.trucks:
            if t.is_available:
                available_truck = t
                break

        if available_truck is None:
            return

        # Dispatch truck delivery process
        self.env.process(self._truck_delivery_process(available_truck, field, best_buyer, min_buyer_dist))

    def _truck_delivery_process(
        self,
        truck: SimulatedTruck,
        field: SimulatedField,
        buyer: SimulatedBuyer,
        distance_km: float,
    ) -> simpy.events.ProcessGenerator:
        """Simulates truck transit and delivery of baled straw to a commercial buyer."""
        truck.is_available = False
        try:
            # Tonnage hauled is min of truck capacity, field residue, and buyer remaining demand
            tonnes = min(truck.capacity_tonnes, field.residue_tonnes_est, buyer.remaining_demand)
            if tonnes <= 0:
                return

            # Truck speed ~40 km/h; round trip transit
            round_trip_km = distance_km * 2.0
            transit_hours = max(0.5, round_trip_km / 40.0)

            yield self.env.timeout(transit_hours)

            truck.total_km_travelled += round_trip_km
            truck.total_tonnes_hauled += tonnes
            buyer.tonnes_filled += tonnes

            # Farmer earns straw revenue (80% of buyer price after logistics cost)
            revenue = tonnes * buyer.price_inr_per_tonne * 0.8
            farmer = self.state.get_farmer(field.farmer_id)
            farmer.straw_revenue_earned_inr += round(revenue, 2)

        finally:
            truck.is_available = True

    def _finalize_simulation(self) -> None:
        """Computes machine idle hours and farmer net income upon season completion."""
        # Machine idle hours calculation
        for m in self.state.machines:
            busy_time = m.operating_hours + m.transit_hours + m.breakdown_hours
            m.idle_hours = round(max(0.0, self.total_season_hours - busy_time), 2)
            m.operating_hours = round(m.operating_hours, 2)
            m.transit_hours = round(m.transit_hours, 2)
            m.breakdown_hours = round(m.breakdown_hours, 2)

        # Farmer net income calculation
        for f in self.state.farmers:
            f.net_income_inr = round(
                f.straw_revenue_earned_inr - f.machine_fees_paid_inr - f.burn_cost_penalty_inr, 2
            )

        # Final clock update
        self.clock.set(self.config.season_start + timedelta(hours=self.total_season_hours))
