# Logistics Agent

## Purpose
The Logistics agent coordinates the aggregation, collection, and delivery of baled crop residue from farm fields to industrial buyer off-take facilities (such as bio-CNG plants, biomass power stations, and paper mills). It solves a Vehicle Routing Problem with Time Windows (VRPTW) optimizing both transport monetary costs and CO2 emissions.

## Inputs
- `LogisticsInput`:
  - `pickups`: List of `FieldPickup` nodes (field ID, GPS coordinates, tonnes available, moisture percentage, ready time, deadline).
  - `dropoffs`: List of `BuyerDropoff` facilities (buyer ID, GPS coordinates, moisture spec, capacity, receiving hours).
  - `trucks`: Fleet of commercial trucks (`TruckSpec`) with capacity, per-km cost, CO2 emission factors, and depot locations.
  - `config`: Solver parameters (`RoutingConfig`) including CO2 penalty weights and time limits.
  - `request_explanation`: Boolean flag for LLM explanation generation.

## Outputs
- `LogisticsOutput`:
  - `routes`: Generated `TruckRoute` sequences for each vehicle with arrival/departure timestamps and loading quantities per stop.
  - `total_distance_km`: Cumulative distance driven.
  - `total_cost_inr`: Total freight expenditure in INR.
  - `total_co2_kg`: Estimated emissions from transport.
  - `total_delivered_tonnes`: Biomass successfully aggregated.
  - `unserved_field_ids`: Fields that could not be reached within time windows or vehicle capacity constraints.
  - `solver_status`: Status indicator (`ROUTING_SUCCESS`, `ROUTING_FAIL`).
  - `explanation`: Auditable explanation of routing choices.

## Failure Modes & Fallbacks
- Routing Service Outage: Automatically falls back from OSRM to a haversine distance matrix provider with a 1.3x road winding factor.
- Fleet Capacity Exhaustion: Unserved fields are explicitly returned to the Orchestrator for staged replanning.
