"""Schemas for Buyer Demand agent."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import BuyerType, OrderStatus


class BuyerOrderModel(BaseModel):
    """Represents an industrial residue purchase order."""

    model_config = ConfigDict(extra="forbid")

    order_id: UUID = Field(default_factory=uuid4)
    buyer_id: UUID = Field(default_factory=uuid4)
    buyer_name: str
    buyer_type: BuyerType = BuyerType.BIOMASS_PLANT
    district: str
    tonnes_required: float = Field(..., gt=0.0)
    tonnes_filled: float = Field(0.0, ge=0.0)
    price_inr_per_tonne: float = Field(..., gt=0.0)
    max_moisture_pct: float = Field(15.0, ge=0.0, le=100.0)
    window_start: date
    window_end: date
    status: OrderStatus = OrderStatus.OPEN

    @property
    def open_tonnes(self) -> float:
        return max(0.0, self.tonnes_required - self.tonnes_filled)


class BuyerDemandInput(BaseModel):
    """Input query to aggregate and publish buyer demand."""

    model_config = ConfigDict(extra="forbid")

    district: str
    target_date: date | None = None
    orders: list[BuyerOrderModel] = Field(default_factory=list)
    max_moisture_pct_filter: float | None = None
    request_explanation: bool = True


class OrderBook(BaseModel):
    """Published residue demand order book for a district."""

    model_config = ConfigDict(extra="forbid")

    district: str
    as_of: datetime
    total_tonnes_demanded: float
    total_tonnes_filled: float
    open_tonnes: float
    min_price_inr_per_tonne: float
    max_price_inr_per_tonne: float
    weighted_avg_price_inr_per_tonne: float
    orders: list[BuyerOrderModel]
    explanation: str


class BuyerDemandState(BaseModel):
    """LangGraph execution state for Buyer Demand agent."""

    model_config = ConfigDict(extra="forbid")

    input: BuyerDemandInput
    order_book: OrderBook | None = None
    status: str = "initialized"
