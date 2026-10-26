# ADR-0009: Contract-net auction for decentralized coordination

**Status:** accepted (Phase 3)

**Context.** Centralized solvers assume global information, centralized authority, and low communication latency. In agricultural practice, smallholders, local custom-hiring centers (CHCs), and private machinery operators operate autonomously and protect private schedules and cost structures. We require a decentralized market-like mechanism to coordinate residue clearance without a central planner.

**Decision.** Implement the FIPA Contract-Net Protocol (CNP) with structured multi-attribute bidding and deterministic conflict resolution.

**Design & Protocol Flow.**
1. **Task Announcement (CFP)**: When a field is harvested, the field agent broadcasts a Call for Proposals specifying field acreage, location, residue type, eligible machine types, and sowing deadline.
2. **Bidding**: Available or soon-to-be-available machine agents compute candidate insertion into their itinerary and submit bids specifying:
   - Promised service start hour and estimated completion hour.
   - Quoted hourly price (INR).
   - Empty transit distance from current location to field.
   - Historical completion reliability/reputation.
3. **Bid Evaluation & Conflict Resolution**: The announcing agent evaluates competing bids using a composite utility score:
   $$\text{Utility} = W_{\text{time}} \cdot (\text{Deadline} - \text{Completion}) - W_{\text{cost}} \cdot \text{TotalCost} - W_{\text{dist}} \cdot \text{TransitKm}$$
4. **Award & Contract**: Winning contractor is issued an `Award`.
5. **Auditable Tie-Breaking**: All multi-bid selections record a typed `TieBreakLog` capturing contenders, criterion applied, and deterministic seed-derived tie-breakers.

**Consequences.** Decentralized execution eliminates single points of failure, scales naturally to large districts, and respects operator autonomy. However, decentralized myopic bidding can lead to sub-optimal global route efficiency compared to centralized CP-SAT under scarce machine scenarios.
