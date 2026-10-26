# ADR-0012: Checkpointing, Memory, and Human-in-the-Loop (HITL) Approvals

## Status
Accepted

## Context
Agricultural operations and crop residue coordination involve high-stakes decisions:
- Machinery dispatch to fields facing tight sowing windows.
- Financial obligations and transport routes.
- Farmer communication subject to consent, privacy, and local contact hour regulations.

Autonomous operations can encounter low solver confidence, severe weather shocks, or potential policy edge cases. In these situations, the system must not blindly execute uncertain actions; instead, it must safely pause, register an auditable approval request, and wait for a cooperative / FPO coordinator to review and resolve the decision before resuming.

Furthermore, agent execution state must be checkpointed to survive process restarts and enable thread-level resumption.

## Decision

1. **Dual-Tier Checkpointer Strategy**:
   - **In-Memory Checkpointing (`MemorySaver`)**: Used in the discrete-event simulator and unit tests for zero I/O overhead and rapid deterministic replay.
   - **Postgres Checkpointing (`PostgresSaver`)**: Used in production and staging deployments, persisting agent thread state across service restarts in the application database.

2. **LangGraph Interrupt Architecture**:
   - The Orchestrator graph evaluates confidence scores and Policy Guard outputs.
   - When confidence drops below the operational threshold (< 0.70) or a policy violation is detected:
     1. An `Approval` record is inserted into the `approvals` table (`status="pending"`).
     2. An `ApprovalRequested` typed event is published to the event bus.
     3. The graph executes `interrupt({"approval_id": approval_id, "reason": reason, ...})`.
     4. Execution halts safely, persisting thread state at the breakpoint.

3. **Approval Resolution and Resumption**:
   - The FPO coordinator reviews the pending approval via API or web UI, updating the database record to `approved` or `rejected`.
   - An `ApprovalResolved` event is emitted.
   - The Orchestrator resumes execution by calling `graph.invoke(Command(resume={"status": "approved", "note": note}), config={"configurable": {"thread_id": ...}})`.
   - If approved, the plan proceeds to execution and persistence; if rejected, a replanning cycle or alternative fallback is initiated.

4. **Dynamic Replanning on State Shocks**:
   - Reactive triggers (`rain_forecast_change`, `machine_breakdown`, `burn_detected`) emit a `ReplanTriggered` event.
   - The Orchestrator creates a new versioned plan (`version = previous.version + 1`, `parent_plan_id = previous.id`) and marks the previous plan as `SUPERSEDED`.

## Consequences

### Positive
- Fully auditable human-in-the-loop oversight for high-risk or low-confidence decisions.
- Seamless thread resumption without lost state or duplicate processing.
- Clean separation between automated solver workflows and human supervisory control.

### Negative
- Requires maintaining checkpointer schemas and active thread identifiers.
- Workflows can be blocked indefinitely if human operators do not resolve approvals in a timely manner (addressed by timeout fallbacks).
