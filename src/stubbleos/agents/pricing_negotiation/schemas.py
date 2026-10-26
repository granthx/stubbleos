"""Typed contracts for Pricing & Negotiation agent (Phase 4 skeleton, full in Phase 6)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import LandholdingClass, ServiceType


class TariffQuote(BaseModel):
    """Quoted service tariff structure."""

    model_config = ConfigDict(extra="forbid")

    base_rate_inr: float = Field(..., gt=0.0)
    subsidy_discount_inr: float = Field(0.0, ge=0.0)
    net_price_inr: float = Field(..., ge=0.0)
    rationale: str


class PricingInput(BaseModel):
    """Input parameters to generate a tariff quote."""

    model_config = ConfigDict(extra="forbid")

    farmer_id: UUID
    field_id: UUID
    landholding_class: LandholdingClass
    service_type: ServiceType
    area_acres: float = Field(..., gt=0.0)


class PricingOutput(BaseModel):
    """Evaluated price quote."""

    model_config = ConfigDict(extra="forbid")

    quote: TariffQuote
    is_concessional: bool


class PricingState(BaseModel):
    """LangGraph state for Pricing & Negotiation agent."""

    model_config = ConfigDict(extra="forbid")

    input: PricingInput
    output: PricingOutput | None = None
    status: str = "initialized"
