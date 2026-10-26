"""CP-SAT machine scheduling model for crop residue coordination."""

from __future__ import annotations

import time
from uuid import UUID

from ortools.sat.python import cp_model
from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import LandholdingClass, MachineType
from stubbleos.simulation.model import haversine_distance_km

FAIRNESS_MULTIPLIERS: dict[LandholdingClass, float] = {
    LandholdingClass.MARGINAL: 2.5,
    LandholdingClass.SMALL: 1.8,
    LandholdingClass.SEMI_MEDIUM: 1.2,
    LandholdingClass.MEDIUM: 1.0,
    LandholdingClass.LARGE: 0.8,
}


class JobRequest(BaseModel):
    """Request for machine residue service on a harvested field."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    farmer_id: UUID
    landholding_class: LandholdingClass
    area_acres: float = Field(..., gt=0.0)
    earliest_start_hour: float = Field(..., ge=0.0)
    deadline_hour: float = Field(..., ge=0.0)
    center_lat: float
    center_lon: float
    eligible_machine_types: list[MachineType]
    priority_weight: float = 1.0


class MachineResource(BaseModel):
    """Available machine resource for scheduling."""

    model_config = ConfigDict(extra="forbid")

    machine_id: UUID
    machine_type: MachineType
    capacity_acres_per_hour: float = Field(..., gt=0.0)
    hourly_cost_inr: float = Field(..., ge=0.0)
    current_lat: float
    current_lon: float
    available_from_hour: float = 0.0


class OperatorResource(BaseModel):
    """Certified operator resource."""

    model_config = ConfigDict(extra="forbid")

    operator_id: UUID
    certified_machine_types: list[MachineType]
    is_active: bool = True


class SchedulerConfig(BaseModel):
    """Solver parameters and objective weights for CP-SAT."""

    model_config = ConfigDict(extra="forbid")

    time_limit_seconds: float = Field(5.0, ge=0.0001, le=120.0)
    random_seed: int = 42
    fairness_weight: float = Field(1.5, ge=0.0)
    deadline_weight: float = Field(2.0, ge=0.0)
    transit_speed_kmh: float = Field(25.0, gt=0.0)
    horizon_hours: float = Field(840.0, gt=0.0)


class ScheduledAssignment(BaseModel):
    """A scheduled machine assignment to a field."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    machine_id: UUID
    operator_id: UUID | None = None
    start_hour: float
    duration_hours: float
    end_hour: float
    transit_hours: float
    transit_distance_km: float
    is_on_time: bool


class SchedulerOutput(BaseModel):
    """Output plan and solver telemetry from the machine scheduler."""

    model_config = ConfigDict(extra="forbid")

    assignments: list[ScheduledAssignment]
    unassigned_field_ids: list[UUID]
    solver_status: str
    wall_time_seconds: float
    objective_value: float
    is_fallback: bool = False


def solve_schedule(
    jobs: list[JobRequest],
    machines: list[MachineResource],
    operators: list[OperatorResource] | None = None,
    config: SchedulerConfig | None = None,
) -> SchedulerOutput:
    """Solve the machine-to-field assignment problem using CP-SAT with greedy fallback."""
    cfg = config or SchedulerConfig()
    start_wall_time = time.perf_counter()

    if not jobs or not machines:
        return SchedulerOutput(
            assignments=[],
            unassigned_field_ids=[j.field_id for j in jobs],
            solver_status="NO_JOBS_OR_MACHINES",
            wall_time_seconds=round(time.perf_counter() - start_wall_time, 4),
            objective_value=0.0,
            is_fallback=False,
        )

    # Time discretization: 1 unit = 0.1 hour (6 minutes)
    time_scale = 10
    horizon_units = int(cfg.horizon_hours * time_scale)

    model = cp_model.CpModel()

    # Precompute machine-job transit and durations
    # keys: (field_id, machine_id)
    durations: dict[tuple[UUID, UUID], int] = {}
    transit_units: dict[tuple[UUID, UUID], int] = {}
    transit_km: dict[tuple[UUID, UUID], float] = {}

    for j in jobs:
        for m in machines:
            if m.machine_type in j.eligible_machine_types:
                dur_h = max(0.1, j.area_acres / m.capacity_acres_per_hour)
                durations[(j.field_id, m.machine_id)] = max(1, round(dur_h * time_scale))

                dist = haversine_distance_km(m.current_lat, m.current_lon, j.center_lat, j.center_lon)
                transit_km[(j.field_id, m.machine_id)] = dist
                tr_h = max(0.05, dist / cfg.transit_speed_kmh)
                transit_units[(j.field_id, m.machine_id)] = max(1, round(tr_h * time_scale))

    # Decision variables
    x_vars: dict[tuple[UUID, UUID], cp_model.IntVar] = {}
    interval_vars: dict[tuple[UUID, UUID], cp_model.IntervalVar] = {}
    start_vars: dict[tuple[UUID, UUID], cp_model.IntVar] = {}
    end_vars: dict[tuple[UUID, UUID], cp_model.IntVar] = {}
    on_time_vars: dict[tuple[UUID, UUID], cp_model.IntVar] = {}

    machine_intervals: dict[UUID, list[cp_model.IntervalVar]] = {m.machine_id: [] for m in machines}
    job_assignments: dict[UUID, list[cp_model.IntVar]] = {j.field_id: [] for j in jobs}

    for j in jobs:
        earliest_start_u = round(j.earliest_start_hour * time_scale)
        deadline_u = round(j.deadline_hour * time_scale)

        for m in machines:
            if (j.field_id, m.machine_id) not in durations:
                continue

            dur_u = durations[(j.field_id, m.machine_id)]
            tr_u = transit_units[(j.field_id, m.machine_id)]
            m_avail_u = round(m.available_from_hour * time_scale)
            earliest_possible = max(earliest_start_u, m_avail_u + tr_u)

            if earliest_possible + dur_u > horizon_units:
                continue

            x = model.new_bool_var(f"x_{j.field_id}_{m.machine_id}")
            start = model.new_int_var(earliest_possible, horizon_units, f"start_{j.field_id}_{m.machine_id}")
            end = model.new_int_var(
                earliest_possible + dur_u, horizon_units, f"end_{j.field_id}_{m.machine_id}"
            )
            interval = model.new_optional_interval_var(
                start, dur_u, end, x, f"interval_{j.field_id}_{m.machine_id}"
            )

            on_time = model.new_bool_var(f"on_time_{j.field_id}_{m.machine_id}")
            model.add(end <= deadline_u).only_enforce_if([x, on_time])
            model.add(end > deadline_u).only_enforce_if([x, on_time.Not()])
            model.add(on_time == 0).only_enforce_if(x.Not())

            x_vars[(j.field_id, m.machine_id)] = x
            start_vars[(j.field_id, m.machine_id)] = start
            end_vars[(j.field_id, m.machine_id)] = end
            interval_vars[(j.field_id, m.machine_id)] = interval
            on_time_vars[(j.field_id, m.machine_id)] = on_time

            machine_intervals[m.machine_id].append(interval)
            job_assignments[j.field_id].append(x)

    # 1. At most one machine per job
    for j in jobs:
        assigned = job_assignments[j.field_id]
        if assigned:
            model.add(sum(assigned) <= 1)

    # 2. One job at a time per machine (no overlap)
    for m in machines:
        intervals = machine_intervals[m.machine_id]
        if intervals:
            model.add_no_overlap(intervals)

    # 3. Objective formulation
    # Objective = sum(x * BaseFairnessReward + on_time * DeadlineBonus - TransitPenalty)
    objective_terms: list[cp_model.LinearExpr] = []

    for j in jobs:
        f_mult = FAIRNESS_MULTIPLIERS.get(j.landholding_class, 1.0)
        base_reward = round(100.0 * f_mult * cfg.fairness_weight * j.priority_weight)
        deadline_bonus = round(250.0 * f_mult * cfg.deadline_weight * j.priority_weight)

        for m in machines:
            if (j.field_id, m.machine_id) in x_vars:
                x = x_vars[(j.field_id, m.machine_id)]
                on_time = on_time_vars[(j.field_id, m.machine_id)]
                dist = transit_km[(j.field_id, m.machine_id)]
                dist_penalty = round(dist * 2.0)

                objective_terms.append(x * base_reward)
                objective_terms.append(on_time * deadline_bonus)
                objective_terms.append(x * (-dist_penalty))

    if objective_terms:
        model.maximize(sum(objective_terms))

    # Solver setup
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.time_limit_seconds
    solver.parameters.random_seed = cfg.random_seed
    solver.parameters.num_workers = 1  # Deterministic single-thread solver execution

    status = solver.solve(model)
    status_name = solver.status_name(status)

    # Check if feasible solution found
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments: list[ScheduledAssignment] = []
        assigned_jobs: set[UUID] = set()

        # Simple operator assignment if operators available
        free_operators = list(operators) if operators else []

        for (f_id, m_id), x in x_vars.items():
            if solver.value(x) == 1:
                start_h = round(solver.value(start_vars[(f_id, m_id)]) / time_scale, 2)
                end_h = round(solver.value(end_vars[(f_id, m_id)]) / time_scale, 2)
                dur_h = round(durations[(f_id, m_id)] / time_scale, 2)
                dist_val = round(transit_km[(f_id, m_id)], 2)
                tr_h = round(transit_units[(f_id, m_id)] / time_scale, 2)
                is_ot = bool(solver.value(on_time_vars[(f_id, m_id)]) == 1)

                # Find certified operator
                op_id: UUID | None = None
                m_type = next(m.machine_type for m in machines if m.machine_id == m_id)
                for op in free_operators:
                    if op.is_active and m_type in op.certified_machine_types:
                        op_id = op.operator_id
                        break

                assignments.append(
                    ScheduledAssignment(
                        field_id=f_id,
                        machine_id=m_id,
                        operator_id=op_id,
                        start_hour=start_h,
                        duration_hours=dur_h,
                        end_hour=end_h,
                        transit_hours=tr_h,
                        transit_distance_km=dist_val,
                        is_on_time=is_ot,
                    )
                )
                assigned_jobs.add(f_id)

        # Sort assignments chronologically by start time
        assignments.sort(key=lambda a: a.start_hour)
        unassigned = [j.field_id for j in jobs if j.field_id not in assigned_jobs]

        return SchedulerOutput(
            assignments=assignments,
            unassigned_field_ids=unassigned,
            solver_status=status_name,
            wall_time_seconds=round(time.perf_counter() - start_wall_time, 4),
            objective_value=float(solver.objective_value),
            is_fallback=False,
        )

    # Fallback to greedy Earliest-Deadline-First heuristic
    return _greedy_edf_fallback(jobs, machines, cfg, start_wall_time)


def _greedy_edf_fallback(
    jobs: list[JobRequest],
    machines: list[MachineResource],
    cfg: SchedulerConfig,
    start_time: float,
) -> SchedulerOutput:
    """Deterministic greedy fallback assigning machines by earliest deadline first."""
    sorted_jobs = sorted(
        jobs, key=lambda j: (j.deadline_hour, -FAIRNESS_MULTIPLIERS.get(j.landholding_class, 1.0))
    )

    machine_avail: dict[UUID, float] = {m.machine_id: m.available_from_hour for m in machines}
    machine_loc: dict[UUID, tuple[float, float]] = {
        m.machine_id: (m.current_lat, m.current_lon) for m in machines
    }

    assignments: list[ScheduledAssignment] = []
    assigned_jobs: set[UUID] = set()

    for job in sorted_jobs:
        best_m: MachineResource | None = None
        best_start = float("inf")
        best_transit_h = 0.0
        best_dist = 0.0
        best_dur_h = 0.0

        for m in machines:
            if m.machine_type not in job.eligible_machine_types:
                continue

            loc = machine_loc[m.machine_id]
            dist = haversine_distance_km(loc[0], loc[1], job.center_lat, job.center_lon)
            transit_h = max(0.05, dist / cfg.transit_speed_kmh)
            ready_h = max(job.earliest_start_hour, machine_avail[m.machine_id] + transit_h)
            dur_h = max(0.1, job.area_acres / m.capacity_acres_per_hour)

            if ready_h < best_start:
                best_start = ready_h
                best_m = m
                best_transit_h = transit_h
                best_dist = dist
                best_dur_h = dur_h

        if best_m is not None and best_start + best_dur_h <= cfg.horizon_hours:
            end_h = best_start + best_dur_h
            is_ot = end_h <= job.deadline_hour

            assignments.append(
                ScheduledAssignment(
                    field_id=job.field_id,
                    machine_id=best_m.machine_id,
                    start_hour=round(best_start, 2),
                    duration_hours=round(best_dur_h, 2),
                    end_hour=round(end_h, 2),
                    transit_hours=round(best_transit_h, 2),
                    transit_distance_km=round(best_dist, 2),
                    is_on_time=is_ot,
                )
            )
            assigned_jobs.add(job.field_id)
            machine_avail[best_m.machine_id] = end_h
            machine_loc[best_m.machine_id] = (job.center_lat, job.center_lon)

    unassigned = [j.field_id for j in jobs if j.field_id not in assigned_jobs]

    return SchedulerOutput(
        assignments=assignments,
        unassigned_field_ids=unassigned,
        solver_status="FALLBACK_GREEDY",
        wall_time_seconds=round(time.perf_counter() - start_time, 4),
        objective_value=float(len(assignments) * 100),
        is_fallback=True,
    )
