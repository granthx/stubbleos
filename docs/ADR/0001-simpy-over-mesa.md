# ADR-0001: SimPy for the district simulator

**Status:** accepted (Phase 1; implemented in Phase 2)

**Context.** We need a reproducible simulator with machine breakdowns, rain shocks, truck availability and farmer decisions on a deadline. Options: Mesa (agent-based, grid/space oriented) or SimPy (discrete-event, process and resource oriented).

**Decision.** SimPy, with NumPy `Generator` instances seeded per run.

**Why.** Machines are naturally resources with queues and interrupts (breakdowns); farmers are processes with timed decisions. We do not need Mesa's grid space, and Mesa's scheduler API has changed between major versions, which is a reproducibility risk for results we want to keep re-runnable.

**Consequences.** We write our own agent-behavior layer and metrics collection. All randomness must flow from the run seed; `SimClock` and `SeededUUIDFactory` (Phase 1) exist for this.
