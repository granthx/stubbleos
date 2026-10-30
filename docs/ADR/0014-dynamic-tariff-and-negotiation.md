# ADR 0014: Dynamic Tiered Tariff and Multi-turn Biomass Negotiation

**Status:** accepted (Phase 6)  
**Date:** 2026-10-30  
**Context:** StubbleOS Phase 6 (Pricing & Negotiation)

## Context

The paddy harvest window in Northwest India is intensely compressed (15 to 20 days). During this peak period:
1. Demand for Custom Hiring Centre (CHC) machinery (Super Seeders, Happy Seeders, Balers) spikes dramatically, risking predatory surge pricing that punishes resource-poor farmers.
2. Marginal (<1 ha / 2.5 acres) and small (<2 ha / 5 acres) farmers operate on razor-thin margins and will burn residue if machine rental costs exceed burning alternatives.
3. Industrial straw buyers (biomass power plants, CBG plants, paper mills) require reliable volume and dry straw (<14% moisture) but often submit low bids that fail to cover baling and haulage costs.

## Decision

1. **Tiered Equity & Smallholder Concessions**:
   - Marginal and smallholder farmers receive a guaranteed 25% to 35% cooperative cross-subsidy discount on machine services.
   - Concessional farmers are legally exempt from peak-window surge pricing.
   - Larger landholders pay standard tariffs with a modest, capped surge (10% to 15%) when deadlines are imminent or local machine supply is severely constrained.

2. **Three-Way Fair Settlement**:
   - Total service value is partitioned transparently:
     - 75% to Equipment Owner / CHC operator.
     - 15% to Logistics / Transporter.
     - 10% to StubbleOS Platform coordination pool (funding smallholder subsidies).

3. **Multi-Turn Biomass Bargaining Protocol**:
   - Industrial buyer bids are evaluated against district reservation prices (e.g. ₹1,600/t ex-field, ₹2,000/t CIF plant gate).
   - Unviable low bids (<75% reservation price) are rejected immediately to protect farmer and transporter livelihoods.
   - Acceptable bids trigger automated contract generation; intermediate bids engage a multi-turn concession curve (Boulware-inspired strategy) that converges toward agreement across up to 5 rounds.

4. **Cryptographic Integrity Fingerprint**:
   - Every negotiated agreement generates an immutable `ContractTermsDraft` stamped with a SHA-256 hash chaining farmer ID, buyer ID, field ID, agreed volume, and final tariff.

## Consequences

- Prevents monopolistic price gouging during the critical burning window.
- Guarantees financial viability for baler operators and transport fleets.
- Provides tamper-evident audit trails for registry verification and carbon credit validation.
