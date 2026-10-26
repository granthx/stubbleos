# ADR-0008: Vehicle Routing Problem (VRP) for straw logistics

**Status:** accepted (Phase 3)

**Context.** Following ex-situ baling, straw bales must be transported from farm fields to regional industrial offtakers (biomass power plants, compressed biogas plants, paperboard mills). Transport must respect:
1. Truck carrying capacities (typically 10 tonnes).
2. Offtaker delivery time windows and gate operating hours.
3. Moisture content thresholds (power plants require $\le 16\%$ moisture; CBG plants tolerate up to $22\%$).
4. Dual objectives of minimizing financial logistics freight costs and transportation carbon emissions ($\text{CO}_2$).

**Decision.** Use OR-Tools Vehicle Routing Problem with Time Windows (`pywrapcp.RoutingModel` / `RoutingIndexManager`).

**Formulation & Objective.**
- Fleet: Homogeneous or heterogeneous commercial truck fleet starting and ending at central or peripheral depots.
- Demand dimension: Cumulative truck payload dimension constrained by `truck.capacity_tonnes`.
- Time dimension: Cumulative transit and service time with pickup/delivery time windows and maximum route duration bounds.
- Moisture compatibility: Hard filter prohibiting assignment of high-moisture straw pickups to moisture-sensitive offtakers.
- Objective function: Joint minimization of monetary cost and carbon footprint:
  $$\min \sum_{r \in \text{Routes}} \sum_{(i, j) \in r} \left( \text{CostPerKm}_r \cdot d_{ij} + \lambda_{\text{CO}_2} \cdot \text{EmissionsPerKm} \cdot d_{ij} \right)$$
  where $\lambda_{\text{CO}_2}$ is the societal or carbon credit valuation factor for transport emissions.
- Distance & Routing Provider: Abstract `DistanceMatrixProvider` interface supporting an OSRM HTTP client for real-world road networks, with automatic fallback to Haversine distance matrix with 1.3x road winding factor when OSRM is offline.

**Consequences.** Generates consolidated, multi-stop truck routes with high payload utilization. Requires distance matrix preprocessing across active pickup and drop-off nodes.
