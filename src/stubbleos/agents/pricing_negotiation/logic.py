"""Logic and tariff computation for Pricing & Negotiation agent."""

from __future__ import annotations

from stubbleos.agents.pricing_negotiation.schemas import (
    PricingInput,
    PricingOutput,
    TariffQuote,
)
from stubbleos.core.types import LandholdingClass


def calculate_pricing(input_data: PricingInput) -> PricingOutput:
    """Calculates fair, tiered service pricing with marginal/smallholder concessions."""
    base_rate_per_acre = 1200.0
    total_base = base_rate_per_acre * input_data.area_acres

    # Concessional discount for marginal and small farmers
    is_concessional = input_data.landholding_class in {
        LandholdingClass.MARGINAL,
        LandholdingClass.SMALL,
    }
    subsidy = (total_base * 0.25) if is_concessional else 0.0
    net = total_base - subsidy

    rationale = f"Base rate ₹{base_rate_per_acre:.0f}/acre for {input_data.area_acres:.1f} acres. " + (
        "Includes 25% FPO smallholder cooperative discount." if is_concessional else "Standard tariff."
    )

    quote = TariffQuote(
        base_rate_inr=round(total_base, 2),
        subsidy_discount_inr=round(subsidy, 2),
        net_price_inr=round(net, 2),
        rationale=rationale,
    )
    return PricingOutput(quote=quote, is_concessional=is_concessional)
