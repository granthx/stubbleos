"""Schemas for Policy & Safety Guard agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import Channel, ConsentPurpose


class PolicyViolation(BaseModel):
    """Represents a rule violation detected during policy evaluation."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    severity: Literal["info", "warning", "blocking"]
    action_ref: str
    detail: str


class PolicyCheckRequest(BaseModel):
    """Outbound action to be validated by the Policy & Safety Guard."""

    model_config = ConfigDict(extra="forbid")

    action_ref: str
    farmer_id: UUID | None = None
    purpose: ConsentPurpose = ConsentPurpose.OUTREACH
    channel: Channel = Channel.WHATSAPP
    timestamp: datetime | None = None
    proposed_price_inr_per_tonne: float | None = None
    price_bounds: tuple[float, float] | None = None
    message_text: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class PolicyCheckResult(BaseModel):
    """Outcome of policy evaluation."""

    model_config = ConfigDict(extra="forbid")

    is_allowed: bool
    action_ref: str
    violations: list[PolicyViolation] = Field(default_factory=list)
    rule_evaluations: dict[str, bool] = Field(default_factory=dict)


class PolicyGuardState(BaseModel):
    """State schema for Policy Guard LangGraph execution."""

    model_config = ConfigDict(extra="forbid")

    request: PolicyCheckRequest
    result: PolicyCheckResult | None = None
    is_allowed: bool = True
    violations: list[PolicyViolation] = Field(default_factory=list)
