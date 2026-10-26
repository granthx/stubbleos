"""Schemas for Logistics agent."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.optimization.routing import (
    BuyerDropoff,
    FieldPickup,
    RoutingConfig,
    TruckRoute,
    TruckSpec,
)


class LogisticsInput(BaseModel):
    """Input parameters for biomass logistics and transport routing."""

    model_config = ConfigDict(extra="forbid")

    pickups: list[FieldPickup]
    dropoffs: list[BuyerDropoff]
    trucks: list[TruckSpec]
    config: RoutingConfig = Field(default_factory=RoutingConfig)
    request_explanation: bool = True


class LogisticsOutput(BaseModel):
    """Output solution from the logistics VRP solver."""

    model_config = ConfigDict(extra="forbid")

    routes: list[TruckRoute]
    total_distance_km: float
    total_cost_inr: float
    total_co2_kg: float
    total_delivered_tonnes: float
    unserved_field_ids: list[UUID]
    solver_status: str
    is_haversine_fallback: bool
    explanation: str


class LogisticsState(BaseModel):
    """LangGraph execution state for Logistics agent."""

    model_config = ConfigDict(extra="forbid")

    input: LogisticsInput
    output: LogisticsOutput | None = None
    routes: list[TruckRoute] = Field(default_factory=list)
    explanation: str = ""
    status: str = "initialized"
