# ADR-0007: CP-SAT for machine scheduling

**Status:** accepted (Phase 3)

**Context.** We need to assign agricultural machinery (Happy Seeders, Super Seeders, Balers, Rakes) to harvested fields across an entire district over a multi-day harvesting season. Key operational constraints include:
1. One-job-at-a-time per machine (no concurrent overlapping field operations).
2. Field readiness constraints (a machine cannot begin before a field is harvested or during rain shocks).
3. Sowing deadlines (wheat sowing windows expire 10–20 days post-harvest; delayed sowing causes winter yield penalties).
4. Machine capacities (acres/hour) and variable inter-field travel transit times.
5. Smallholder fairness (preventing large landholders from monopolizing machinery and starving marginal and small farmers).

**Decision.** Use Google OR-Tools CP-SAT (`ortools.sat.python.cp_model`) as the centralized machine scheduling engine.

**Formulation & Objective.**
- Model time discretely in 0.1-hour (6-minute) increments.
- Represent machine operations on fields as optional interval variables `NewOptionalIntervalVar` with non-overlapping constraints per machine (`AddNoOverlap`).
- Enforce precedence and transit times between consecutive field operations.
- Objective function: Maximize deadline-weighted field clearance with smallholder fairness weighting:
  $$\max \sum_{j \in \text{Fields}} x_j \cdot \left( W_{\text{deadline}} \cdot U_j + W_{\text{fairness}} \cdot F_j \right) - \sum \text{TransitPenalty}$$
  where $U_j = \max(1, \text{Deadline}_j - \text{Start}_j)$ represents deadline slack urgency, and $F_j$ is a fairness weight assigning higher coefficients to marginal ($F=2.5$) and small ($F=1.8$) farmers relative to large holders ($F=1.0$).
- Determinism: Fixed `random_seed` and single-thread or deterministic parallel search in `SatParameters`.
- Time-limited fallback: Hard solver timeout (default 5.0 seconds). If CP-SAT finds a feasible solution within the limit, return the best feasible plan. If no feasible solution is found before timeout, invoke a deterministic Earliest-Deadline-First (EDF) greedy heuristic fallback and explicitly report `is_fallback: true` and `solver_status: "FALLBACK_GREEDY"`.

**Consequences.** Centralized scheduling is globally optimal or near-optimal under perfect district visibility. However, solver runtime scales with the number of fields and machines, necessitating time windows and greedy fallbacks for large problem instances.
