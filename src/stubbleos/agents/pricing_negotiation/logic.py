"""Dynamic tiered tariff computation and buyer biomass negotiation protocol."""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from stubbleos.agents.pricing_negotiation.schemas import (
    BiomassCounterOffer,
    BiomassOffer,
    ContractTermsDraft,
    PricingInput,
    PricingOutput,
    TariffQuote,
)
from stubbleos.core.types import LandholdingClass, ServiceType

# Base tariffs in INR
BASE_TARIFFS_PER_ACRE: dict[ServiceType, float] = {
    ServiceType.IN_SITU_SOWING: 1200.0,
    ServiceType.BALING: 1000.0,
    ServiceType.RAKING: 400.0,
    ServiceType.TRANSPORT: 600.0,
}

RESERVATION_PRICE_EX_FIELD = 1600.0  # INR / tonne
CEILING_PRICE_EX_FIELD = 2100.0  # INR / tonne
TRANSPORT_CIF_SURCHARGE = 400.0  # INR / tonne for CIF plant delivery


def calculate_pricing(input_data: PricingInput) -> PricingOutput:
    """Calculates fair, tiered service pricing with smallholder concessions and surge protection."""
    base_rate_per_acre = BASE_TARIFFS_PER_ACRE.get(input_data.service_type, 1200.0)
    total_base = base_rate_per_acre * input_data.area_acres

    # Concessional discount for marginal and small farmers
    is_concessional = input_data.landholding_class in {
        LandholdingClass.MARGINAL,
        LandholdingClass.SMALL,
    }
    subsidy = (total_base * 0.25) if is_concessional else 0.0

    # Surge & scarcity multiplier (smallholders are protected against surge)
    surge = 0.0
    if not is_concessional:
        if input_data.days_to_deadline is not None and input_data.days_to_deadline <= 5:
            surge += total_base * 0.15
        if input_data.machine_scarcity_ratio > 1.5:
            surge += total_base * 0.10

    # Moisture penalty deduction (>14% moisture incurs ₹50/tonne penalty)
    moisture_penalty = 0.0
    if input_data.moisture_pct is not None and input_data.moisture_pct > 14.0:
        tonnes = input_data.estimated_tonnes or (input_data.area_acres * 2.2)
        excess_moisture = input_data.moisture_pct - 14.0
        moisture_penalty = excess_moisture * 50.0 * tonnes

    net = max(0.0, total_base - subsidy + surge - moisture_penalty)

    # Three-way fair settlement breakdown
    operator_receivable = round(net * 0.75, 2)
    logistics_share = round(net * 0.15, 2)
    platform_fee = round(net * 0.10, 2)

    rationale = (
        f"Base rate ₹{base_rate_per_acre:.0f}/acre for {input_data.area_acres:.1f} acres ({input_data.service_type.value}). "
        + ("Includes 25% FPO smallholder cooperative discount. " if is_concessional else "Standard tariff. ")
        + (f"Surge ₹{surge:.0f} applied for peak window deadline. " if surge > 0 else "")
        + (f"Moisture penalty -₹{moisture_penalty:.0f} (>14% moisture). " if moisture_penalty > 0 else "")
    ).strip()

    quote = TariffQuote(
        base_rate_inr=round(total_base, 2),
        subsidy_discount_inr=round(subsidy, 2),
        surge_amount_inr=round(surge, 2),
        moisture_penalty_inr=round(moisture_penalty, 2),
        net_price_inr=round(net, 2),
        rationale=rationale,
        operator_receivable_inr=operator_receivable,
        logistics_share_inr=logistics_share,
        platform_fee_inr=platform_fee,
    )
    return PricingOutput(quote=quote, is_concessional=is_concessional, confidence=1.0)


def negotiate_biomass_bid(
    offer: BiomassOffer,
    round_number: int = 1,
    reservation_price: float | None = None,
    ceiling_target: float | None = None,
    max_rounds: int = 5,
) -> BiomassCounterOffer:
    """Executes multi-turn Contract-Net price bargaining with industrial biomass buyers."""
    is_cif = offer.delivery_term == "cif_plant"
    res_price = (reservation_price or RESERVATION_PRICE_EX_FIELD) + (
        TRANSPORT_CIF_SURCHARGE if is_cif else 0.0
    )
    ceil_price = (ceiling_target or CEILING_PRICE_EX_FIELD) + (TRANSPORT_CIF_SURCHARGE if is_cif else 0.0)

    offered = offer.proposed_price_per_tonne_inr

    # Case 1: Buyer offer meets or exceeds reservation price -> Accept
    if offered >= res_price:
        return BiomassCounterOffer(
            buyer_id=offer.buyer_id,
            order_id=offer.order_id,
            round_number=round_number,
            counter_price_per_tonne_inr=offered,
            accepted=True,
            walk_away=False,
            rationale=f"Offer ₹{offered:.0f}/t meets minimum reservation threshold (₹{res_price:.0f}/t). Deal accepted.",
        )

    # Case 2: Unreasonably low bid (below 75% of reservation) -> Immediate walk-away
    walk_away_floor = res_price * 0.75
    if offered < walk_away_floor:
        return BiomassCounterOffer(
            buyer_id=offer.buyer_id,
            order_id=offer.order_id,
            round_number=round_number,
            counter_price_per_tonne_inr=res_price,
            accepted=False,
            walk_away=True,
            rationale=f"Offered ₹{offered:.0f}/t is below economic viability floor (₹{walk_away_floor:.0f}/t). Terminating negotiation.",
        )

    # Case 3: Reached maximum negotiation rounds without agreement -> Walk away
    if round_number >= max_rounds:
        return BiomassCounterOffer(
            buyer_id=offer.buyer_id,
            order_id=offer.order_id,
            round_number=round_number,
            counter_price_per_tonne_inr=res_price,
            accepted=False,
            walk_away=True,
            rationale=f"Maximum rounds ({max_rounds}) exceeded without reaching agreed reservation price ₹{res_price:.0f}/t.",
        )

    # Case 4: Generate counter-offer using concession curve
    progress = (round_number - 1) / max(1, max_rounds - 1)
    concession = (ceil_price - res_price) * (progress**0.8)
    counter_price = round(max(res_price, ceil_price - concession), 2)

    return BiomassCounterOffer(
        buyer_id=offer.buyer_id,
        order_id=offer.order_id,
        round_number=round_number,
        counter_price_per_tonne_inr=counter_price,
        accepted=False,
        walk_away=False,
        rationale=f"Round {round_number}/{max_rounds}: Buyer offered ₹{offered:.0f}/t. StubbleOS counter-offers ₹{counter_price:.0f}/t ({offer.delivery_term}).",
    )


def draft_contract_terms(
    field_id: UUID,
    farmer_id: UUID,
    buyer_id: UUID | None,
    price_per_tonne_inr: float,
    tonnes_agreed: float,
    delivery_term: str = "ex_field",
    order_id: UUID | None = None,
) -> ContractTermsDraft:
    """Generates an immutable contract draft stamped with a SHA-256 fingerprint."""
    contract_id = uuid4()
    raw_payload = f"{contract_id}:{field_id}:{farmer_id}:{buyer_id}:{price_per_tonne_inr}:{tonnes_agreed}:{delivery_term}"
    sha = hashlib.sha256(raw_payload.encode()).hexdigest()

    summary = (
        f"Contract {contract_id}: Supply of {tonnes_agreed:.1f}t paddy straw at ₹{price_per_tonne_inr:.2f}/t "
        f"({delivery_term}). Verified SHA-256: {sha[:16]}..."
    )

    return ContractTermsDraft(
        contract_id=contract_id,
        order_id=order_id,
        field_id=field_id,
        farmer_id=farmer_id,
        buyer_id=buyer_id,
        price_per_tonne_inr=price_per_tonne_inr,
        tonnes_agreed=tonnes_agreed,
        delivery_term=delivery_term,
        contract_sha256=sha,
        terms_summary=summary,
    )
