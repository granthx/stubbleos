# Buyer Demand Agent

## Purpose
The Buyer Demand agent tracks, models, and aggregates purchase orders from commercial residue offtakers (biomass power stations, compressed biogas/CBG producers, paper mills, and packaging manufacturers). It consolidates procurement orders into an auditable district Order Book, calculating volume-weighted prices and moisture tolerances.

## Inputs
- `BuyerDemandInput`:
  - `district`: Target district identifier.
  - `target_date`: Optional delivery date filter.
  - `orders`: Collection of `BuyerOrderModel` records.
  - `max_moisture_pct_filter`: Optional threshold filtering out buyers with strict moisture limits.
  - `request_explanation`: Boolean flag for natural language commentary.

## Outputs
- `OrderBook`:
  - `district`: Target district.
  - `as_of`: Timestamp of publication in IST.
  - `total_tonnes_demanded`: Cumulative biomass tonnage contracted.
  - `total_tonnes_filled`: Biomass delivered so far.
  - `open_tonnes`: Unfilled demand capacity.
  - `min_price_inr_per_tonne`: Floor price across active orders.
  - `max_price_inr_per_tonne`: Ceiling price across active orders.
  - `weighted_avg_price_inr_per_tonne`: Volume-weighted market price in INR.
  - `orders`: Filtered matching order list.
  - `explanation`: Agent analysis of off-take demand.

## Failure Modes
- Empty Order Book: Gracefully returns zero demand metrics and flags a supply-demand mismatch to the Orchestrator.
- Incompatible Moisture: Filters out orders where field moisture exceeds buyer specs.
