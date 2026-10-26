# ADR-0011: LangGraph State Design for Multi-Agent Coordination

## Status
Accepted

## Context
In Phase 4, StubbleOS coordinates autonomous agents (Supervisor Orchestrator, Machine Scheduler, Logistics, Buyer Demand, Policy Guard, and Sensing/Interaction specialist agents). We require a deterministic, auditable, and type-safe architecture for state representation and transitions across agent graphs.

Unstructured message passing or shared mutable memory creates failure modes:
1. Nondeterministic race conditions between parallel scheduling and logistics tasks.
2. Unaudited state mutations where LLMs or specialist nodes accidentally modify optimizer decisions.
3. Inability to reproduce exact decisions in discrete-event simulation and replay.

## Decision

1. **Typed Immutable Contracts via Pydantic & TypedDict**:
   - Every LangGraph graph defines a concrete `State` TypedDict with explicit typed fields.
   - All input requests, solver outputs, and event payloads use strict Pydantic models (`StrictModel` / `ConfigDict(extra="forbid")`).
   - Node functions are pure reducers: they receive an immutable state snapshot and return a dictionary of state updates.

2. **Hard Separation between Optimizers and LLMs**:
   - Machine allocations, route itineraries, and pricing formulas are computed strictly by deterministic algorithms (OR-Tools CP-SAT, VRP, and the Contract-Net auction).
   - LLMs (`FakeLLM` in tests/simulation, Groq/Anthropic in production) are strictly restricted to:
     - Generating natural-language explanations of decisions.
     - Conversational framing for farmers and buyers.
   - The LLM node has no write-access to assignment lists or route waypoints, making hallucinated machine schedules structurally impossible.

3. **Hierarchical Supervisor Pattern**:
   - The `Orchestrator` serves as the supervisor graph, delegating sub-problems to specialist sub-graphs (`buyer_demand`, `machine_scheduler`, `logistics`, `policy_guard`).
   - The Orchestrator manages the aggregate per-district per-day plan, tracks replan triggers, evaluates plan confidence, and routes policy violations to the human approval queue.

4. **Deterministic Simulation Parity**:
   - In simulation mode, all agent invocations utilize `FakeLLM` and an injected `Clock` / `IdFactory`.
   - Node execution order and state reduction are completely deterministic given the same random seed.

## Consequences

### Positive
- Strict compile-time and runtime type checking across all agent boundaries.
- Eliminates risk of LLM hallucinations corrupting mission-critical field operations.
- State history is fully serializable to JSON and compatible with LangGraph checkpointers.

### Negative
- Requires explicit schema boilerplate for every agent input, output, and intermediate state.
