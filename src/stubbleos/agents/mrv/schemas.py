"""Typed contracts for MRV agent (Phase 4 skeleton, full in Phase 6)."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ImpactEstimate(BaseModel):
    """Indicative impact and emissions reduction calculation."""

    model_config = ConfigDict(extra="forbid")

    burn_avoided: bool
    area_acres: float
    co2e_kg_avoided: float
    record_sha256: str
    method_note: str = "indicative impact record (not registry-verified)"


class MrvInput(BaseModel):
    """Input parameters to generate MRV evidence."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    area_acres: float = Field(..., gt=0.0)
    season: str = "2026_kharif"
    burn_avoided: bool = True


class MrvOutput(BaseModel):
    """Generated MRV proof package."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID = Field(default_factory=uuid4)
    field_id: UUID
    impact: ImpactEstimate


class MrvState(BaseModel):
    """LangGraph state for MRV agent."""

    model_config = ConfigDict(extra="forbid")

    input: MrvInput
    output: MrvOutput | None = None
    status: str = "initialized"
