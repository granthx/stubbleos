"""Unit tests for Phase 6 Pricing & Negotiation agent."""

from __future__ import annotations

import uuid

from stubbleos.agents.pricing_negotiation.graph import build_pricing_negotiation_graph
from stubbleos.agents.pricing_negotiation.logic import (
    calculate_pricing,
    draft_contract_terms,
    negotiate_biomass_bid,
)
from stubbleos.agents.pricing_negotiation.schemas import (
    BiomassOffer,
    PricingInput,
    PricingState,
)
from stubbleos.core.types import LandholdingClass, ServiceType


def test_concessional_pricing_and_surge_protection() -> None:
    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()

    # 1. Marginal farmer (<2.5 acres): gets 25% FPO subsidy discount, protected from surge
    inp_marginal = PricingInput(
        farmer_id=f_id,
        field_id=fld_id,
        landholding_class=LandholdingClass.MARGINAL,
        service_type=ServiceType.IN_SITU_SOWING,
        area_acres=2.0,
        days_to_deadline=2,  # Urgent deadline
        machine_scarcity_ratio=2.0,  # High scarcity
    )
    out_marginal = calculate_pricing(inp_marginal)
    assert out_marginal.is_concessional is True
    assert out_marginal.quote.base_rate_inr == 2400.0  # 2 acres * 1200
    assert out_marginal.quote.subsidy_discount_inr == 600.0  # 25% of 2400
    assert out_marginal.quote.surge_amount_inr == 0.0  # Protected from surge!
    assert out_marginal.quote.net_price_inr == 1800.0

    # Settlement breakdown check
    assert out_marginal.quote.operator_receivable_inr == 1350.0  # 75%
    assert out_marginal.quote.logistics_share_inr == 270.0  # 15%
    assert out_marginal.quote.platform_fee_inr == 180.0  # 10%

    # 2. Large farmer: standard rate + surge applied
    inp_large = PricingInput(
        farmer_id=f_id,
        field_id=fld_id,
        landholding_class=LandholdingClass.LARGE,
        service_type=ServiceType.IN_SITU_SOWING,
        area_acres=10.0,
        days_to_deadline=2,  # Urgent deadline -> +15%
        machine_scarcity_ratio=2.0,  # High scarcity -> +10%
    )
    out_large = calculate_pricing(inp_large)
    assert out_large.is_concessional is False
    assert out_large.quote.base_rate_inr == 12000.0
    assert out_large.quote.subsidy_discount_inr == 0.0
    assert out_large.quote.surge_amount_inr == 3000.0  # 25% surge total
    assert out_large.quote.net_price_inr == 15000.0


def test_moisture_penalty_deduction() -> None:
    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()

    # Straw with 18% moisture (excess = 4% over 14% threshold)
    inp_wet = PricingInput(
        farmer_id=f_id,
        field_id=fld_id,
        landholding_class=LandholdingClass.MEDIUM,
        service_type=ServiceType.BALING,
        area_acres=5.0,
        estimated_tonnes=10.0,
        moisture_pct=18.0,
    )
    out = calculate_pricing(inp_wet)
    # Excess moisture = 4.0; Penalty = 4.0 * 50.0 * 10.0 = 2000.0
    assert out.quote.moisture_penalty_inr == 2000.0
    assert out.quote.net_price_inr == max(0.0, 5000.0 - 2000.0)


def test_biomass_buyer_negotiation_protocol() -> None:
    b_id = uuid.uuid4()
    ord_id = uuid.uuid4()

    # 1. Acceptable offer immediately
    offer_good = BiomassOffer(
        buyer_id=b_id,
        order_id=ord_id,
        proposed_price_per_tonne_inr=1700.0,
        tonnes=100.0,
        delivery_term="ex_field",
    )
    res_good = negotiate_biomass_bid(offer_good)
    assert res_good.accepted is True
    assert res_good.walk_away is False
    assert res_good.counter_price_per_tonne_inr == 1700.0

    # 2. Predatory / unreasonably low offer -> Walk away immediately
    offer_bad = BiomassOffer(
        buyer_id=b_id,
        order_id=ord_id,
        proposed_price_per_tonne_inr=900.0,  # Below 75% of 1600 (1200)
        tonnes=100.0,
        delivery_term="ex_field",
    )
    res_bad = negotiate_biomass_bid(offer_bad)
    assert res_bad.accepted is False
    assert res_bad.walk_away is True

    # 3. Intermediate offer -> Multi-turn counter-offer
    offer_mid = BiomassOffer(
        buyer_id=b_id,
        order_id=ord_id,
        proposed_price_per_tonne_inr=1450.0,
        tonnes=100.0,
        delivery_term="ex_field",
    )
    res_r1 = negotiate_biomass_bid(offer_mid, round_number=1)
    assert res_r1.accepted is False
    assert res_r1.walk_away is False
    assert res_r1.counter_price_per_tonne_inr > 1600.0

    # Round 5 (final round)
    res_r5 = negotiate_biomass_bid(offer_mid, round_number=5, max_rounds=5)
    assert res_r5.walk_away is True  # Buyer did not meet reservation price


def test_contract_drafting_and_sha256_integrity() -> None:
    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()
    b_id = uuid.uuid4()

    draft = draft_contract_terms(
        field_id=fld_id,
        farmer_id=f_id,
        buyer_id=b_id,
        price_per_tonne_inr=1650.0,
        tonnes_agreed=50.0,
        delivery_term="ex_field",
    )

    assert len(draft.contract_sha256) == 64
    assert draft.price_per_tonne_inr == 1650.0
    assert draft.tonnes_agreed == 50.0
    assert "SHA-256" in draft.terms_summary


def test_pricing_negotiation_graph_with_buyer_offer() -> None:
    graph = build_pricing_negotiation_graph()

    f_id = uuid.uuid4()
    fld_id = uuid.uuid4()
    b_id = uuid.uuid4()
    ord_id = uuid.uuid4()

    inp = PricingInput(
        farmer_id=f_id,
        field_id=fld_id,
        landholding_class=LandholdingClass.SMALL,
        service_type=ServiceType.BALING,
        area_acres=3.0,
    )
    buyer_offer = BiomassOffer(
        buyer_id=b_id,
        order_id=ord_id,
        proposed_price_per_tonne_inr=1750.0,  # Acceptable
        tonnes=20.0,
        delivery_term="ex_field",
    )

    state = PricingState(input=inp, buyer_offer=buyer_offer)
    res = graph.invoke(state, config={"configurable": {"thread_id": "pn_phase6_test"}})

    assert res["status"] == "completed"
    assert res["counter_offer"].accepted is True
    assert res["contract_draft"] is not None
    assert res["contract_draft"].price_per_tonne_inr == 1750.0
    assert len(res["contract_draft"].contract_sha256) == 64
