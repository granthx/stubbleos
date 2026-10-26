# Pricing & Negotiation Agent (Phase 4 Skeleton)

## Purpose
The Pricing & Negotiation agent calculates dynamic, tiered machinery and baling tariffs. It incorporates equitable cross-subsidies for marginal and smallholder farmers and negotiates price boundaries with industrial biomass buyers.

## Typed Contract
- Input: `PricingInput` (farmer ID, field ID, landholding class, service type, acreage).
- Output: `PricingOutput` (`TariffQuote` with base rate, discounts, and net price).
- State: `PricingState`.

## Tools
- `compute_dynamic_tariff_mock`: Calculates tiered area-based rates.
