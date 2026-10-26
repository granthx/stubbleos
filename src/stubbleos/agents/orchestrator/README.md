# Orchestrator (Supervisor) Agent

## Purpose
The Orchestrator agent serves as the central supervisor for StubbleOS. It manages the multi-agent lifecycle across each district and operational day. It coordinates sensing, schedules machinery, plans biomass logistics routes, enforces cross-cutting policy compliance, mediates resource conflicts, triggers dynamic replanning upon environmental or mechanical shocks, and escalates uncertain decisions to human coordinators via LangGraph interrupts.

## Inputs
- `OrchestratorInput`:
  - `district`: Target district identifier (e.g. "Sangrur").
  - `plan_date`: Operational calendar date.
  - `strategy`: Optimization strategy (`centralized` or `decentralized`).
  - `jobs`: Harvested fields awaiting clearance (`JobRequest`).
  - `machines`: Machinery fleet (`MachineResource`).
  - `pickups` / `dropoffs` / `trucks`: Logistics transport entities.
  - `orders`: Industrial buyer orders (`BuyerOrderModel`).
  - `replan_trigger`: Optional reactive trigger (`ReplanTriggered`).
  - `previous_plan`: Preceding `DistrictPlan` if executing a replan.
  - `confidence_threshold`: Operational threshold (default 0.70) below which human approval is required.

## Outputs
- `DistrictPlan`:
  - `plan_id`: Unique identifier.
  - `district` / `plan_date` / `strategy` / `version`.
  - `parent_plan_id`: Linked parent plan if superseding.
  - `status`: Plan status (`active`, `superseded`, `failed`).
  - `assignments`: Exact machine assignments from Machine Scheduler.
  - `routes`: Generated delivery routes from Logistics.
  - `confidence`: Calibrated confidence score [0.0, 1.0].
  - `explanation`: Audit summary.

## Dynamic Replanning Loop
Plans are generated daily at dawn and reactively updated when shock events occur:
1. `rain_forecast_change`: Accelerates sowing deadlines to avoid muddy fields.
2. `machine_breakdown`: Removes broken machines from the active pool and reallocates affected tasks.
3. `burn_detected`: Removes burnt fields from the clearing queue.
When replanning, a new plan version is created (`version = parent.version + 1`), and the preceding plan is marked as `SUPERSEDED`.

## Human-in-the-Loop (HITL) Approvals
When plan confidence falls below `confidence_threshold` (< 0.70) or the Policy Guard identifies a blocking violation:
1. An `Approval` record is written to the database (`status="pending"`).
2. An `ApprovalRequested` typed event is emitted.
3. LangGraph executes `interrupt(...)` pausing graph execution.
4. An FPO coordinator reviews the proposal and submits `approved` or `rejected`.
5. Execution resumes via `Command(resume=...)`, writing `ApprovalResolved` and either committing or aborting the plan.
