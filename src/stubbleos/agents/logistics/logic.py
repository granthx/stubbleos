"""Pure logistics VRP solving and explanation logic."""

from __future__ import annotations

from stubbleos.agents.logistics.schemas import LogisticsInput, LogisticsOutput
from stubbleos.llm.base import LLMClient, LLMRequest
from stubbleos.optimization.routing import RoutingOutput, solve_straw_routing


async def generate_logistics_explanation(
    vrp_output: RoutingOutput,
    llm: LLMClient | None = None,
) -> str:
    """Generate an auditable, natural-language explanation of freight routes."""
    fallback_summary = (
        f"Generated {len(vrp_output.routes)} truck routes covering {vrp_output.total_distance_km:.1f} km. "
        f"Total delivered: {vrp_output.total_delivered_tonnes:.1f} tonnes. "
        f"Transport cost: {vrp_output.total_cost_inr:.1f} INR. "
        f"CO2 footprint: {vrp_output.total_co2_kg:.1f} kg. "
        f"Unserved fields: {len(vrp_output.unserved_field_ids)}."
    )

    if llm is None:
        return fallback_summary

    prompt = (
        f"You are the StubbleOS Logistics Dispatch agent. Summarize the biomass transit plan for depot managers:\n"
        f"- Active Routes: {len(vrp_output.routes)}\n"
        f"- Total Distance: {vrp_output.total_distance_km:.1f} km\n"
        f"- Delivered Biomass: {vrp_output.total_delivered_tonnes:.1f} tonnes\n"
        f"- Total Cost: {vrp_output.total_cost_inr:.1f} INR\n"
        f"- Estimated CO2 Emissions: {vrp_output.total_co2_kg:.1f} kg\n"
        f"- Unserved Fields: {len(vrp_output.unserved_field_ids)}\n"
        f"Explain the transport efficiency, route clusters, and environmental trade-offs."
    )
    try:
        response = await llm.generate(
            LLMRequest.simple(user_text=prompt, purpose="logistics_explanation", max_tokens=256)
        )
        return response.text.strip()
    except Exception:
        return fallback_summary


async def run_logistics(
    input_data: LogisticsInput,
    llm: LLMClient | None = None,
) -> LogisticsOutput:
    """Runs the VRP solver and produces an auditable logistics solution."""
    vrp_res = solve_straw_routing(
        pickups=input_data.pickups,
        dropoffs=input_data.dropoffs,
        trucks=input_data.trucks,
        config=input_data.config,
    )

    explanation = ""
    if input_data.request_explanation:
        explanation = await generate_logistics_explanation(vrp_res, llm=llm)

    return LogisticsOutput(
        routes=vrp_res.routes,
        total_distance_km=round(vrp_res.total_distance_km, 2),
        total_cost_inr=round(vrp_res.total_cost_inr, 2),
        total_co2_kg=round(vrp_res.total_co2_kg, 2),
        total_delivered_tonnes=round(vrp_res.total_delivered_tonnes, 2),
        unserved_field_ids=vrp_res.unserved_field_ids,
        solver_status=vrp_res.solver_status,
        is_haversine_fallback=vrp_res.is_haversine_fallback,
        explanation=explanation,
    )
