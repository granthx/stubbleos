# ADR-0010: Agricultural fairness definition and constraint formulation

**Status:** accepted (Phase 3)

**Context.** Market-driven and naive greedy scheduling often favor large landholders because large contiguous plots offer higher machine contractor revenue per setup and lower transit overhead. Marginal (<1 ha) and small (1–2 ha) farmers represent over 65% of farming households in the Indian Agricultural Census, yet are routinely marginalized, forcing them into desperate panic burning when sowing deadlines expire.

**Decision.** Define a formal fairness objective and operational constraint protecting smallholder clearance rates.

**Fairness Definition.**
1. **Landholding Classification**:
   - Smallholders: $\mathcal{S} = \{ f \in \text{Farmers} \mid \text{Class}(f) \in \{\text{MARGINAL}, \text{SMALL}\} \}$.
   - Largeholders: $\mathcal{L} = \{ f \in \text{Farmers} \mid \text{Class}(f) \in \{\text{MEDIUM}, \text{LARGE}\} \}$.
2. **Clearance Rate Metric**:
   $$R(\mathcal{G}) = \frac{\sum_{i \in \text{Fields}(\mathcal{G})} \mathbf{1}_{[\text{Cleared}_i \le \text{Deadline}_i]}}{|\text{Fields}(\mathcal{G})|}$$
3. **Fairness Gap**:
   $$\text{Gap} = R(\mathcal{L}) - R(\mathcal{S})$$
   A positive gap denotes unfairness against smallholders; a fair system maintains $\text{Gap} \le 0$ or within a tight tolerance ($|\text{Gap}| \le 5\%$).

**Implementation in Optimizers & Coordination.**
- **In CP-SAT (`scheduler.py`)**: Smallholder field clearance is weighted with an explicit fairness term $F_j \in [1.8, 2.5]$, ensuring the solver prioritizes smallholder timely clearance even when per-acre travel transit ratios are less favorable.
- **In Auction & Conflict Resolution (`conflicts.py`)**: When smallholder and largeholder jobs contend for the same machine time slot, smallholders receive a priority bonus $B_{\text{small}} > 0$.
- **In Monitoring (`metrics.py`)**: The fairness gap is tracked and reported across all runs.

**Consequences.** Increases operational equity across farming classes and significantly curtails panic burns among resource-poor farmers, while accepting minor trade-offs in machine travel efficiency.
