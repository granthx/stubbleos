"""Pure demand aggregation and order book logic."""

from __future__ import annotations

from datetime import datetime

from stubbleos.agents.buyer_demand.schemas import (
    BuyerDemandInput,
    BuyerOrderModel,
    OrderBook,
)
from stubbleos.core.clock import IST
from stubbleos.core.types import OrderStatus
from stubbleos.llm.base import LLMClient, LLMRequest


async def generate_demand_explanation(
    district: str,
    open_tonnes: float,
    min_price: float,
    max_price: float,
    weighted_avg_price: float,
    order_count: int,
    llm: LLMClient | None = None,
) -> str:
    """Generate natural language commentary on the order book."""
    fallback_summary = (
        f"District {district} has {order_count} active orders seeking {open_tonnes:.1f} open tonnes. "
        f"Price range: {min_price:.1f} to {max_price:.1f} INR/tonne (volume-weighted avg: {weighted_avg_price:.1f} INR)."
    )

    if llm is None:
        return fallback_summary

    prompt = (
        f"You are the StubbleOS Market Demand Analyst. Summarize the commercial offtake situation for district coordinators:\n"
        f"- District: {district}\n"
        f"- Active Buyer Orders: {order_count}\n"
        f"- Open Demand Volume: {open_tonnes:.1f} tonnes\n"
        f"- Minimum Offered Price: {min_price:.1f} INR/tonne\n"
        f"- Maximum Offered Price: {max_price:.1f} INR/tonne\n"
        f"- Weighted Average Price: {weighted_avg_price:.1f} INR/tonne\n"
        f"Highlight buyer purchasing appetite and advice on matching supply."
    )
    try:
        response = await llm.generate(
            LLMRequest.simple(user_text=prompt, purpose="demand_explanation", max_tokens=256)
        )
        return response.text.strip()
    except Exception:
        return fallback_summary


async def build_order_book(
    input_data: BuyerDemandInput,
    llm: LLMClient | None = None,
) -> OrderBook:
    """Aggregates buyer orders, computes volume-weighted prices, and publishes an OrderBook."""
    target_dt = input_data.target_date

    # Filter applicable orders
    matching_orders: list[BuyerOrderModel] = []
    for o in input_data.orders:
        if o.status != OrderStatus.OPEN:
            continue
        if o.district.lower() != input_data.district.lower():
            continue
        if target_dt is not None and not (o.window_start <= target_dt <= o.window_end):
            continue
        if (
            input_data.max_moisture_pct_filter is not None
            and o.max_moisture_pct < input_data.max_moisture_pct_filter
        ):
            continue
        matching_orders.append(o)

    total_demanded = sum(o.tonnes_required for o in matching_orders)
    total_filled = sum(o.tonnes_filled for o in matching_orders)
    open_tonnes = sum(o.open_tonnes for o in matching_orders)

    if matching_orders and open_tonnes > 0:
        min_price = min(o.price_inr_per_tonne for o in matching_orders)
        max_price = max(o.price_inr_per_tonne for o in matching_orders)
        weighted_avg_price = sum(o.price_inr_per_tonne * o.open_tonnes for o in matching_orders) / open_tonnes
    else:
        min_price = 0.0
        max_price = 0.0
        weighted_avg_price = 0.0

    explanation = ""
    if input_data.request_explanation:
        explanation = await generate_demand_explanation(
            district=input_data.district,
            open_tonnes=open_tonnes,
            min_price=min_price,
            max_price=max_price,
            weighted_avg_price=weighted_avg_price,
            order_count=len(matching_orders),
            llm=llm,
        )

    return OrderBook(
        district=input_data.district,
        as_of=datetime.now(IST),
        total_tonnes_demanded=round(total_demanded, 2),
        total_tonnes_filled=round(total_filled, 2),
        open_tonnes=round(open_tonnes, 2),
        min_price_inr_per_tonne=round(min_price, 2),
        max_price_inr_per_tonne=round(max_price, 2),
        weighted_avg_price_inr_per_tonne=round(weighted_avg_price, 2),
        orders=matching_orders,
        explanation=explanation,
    )
