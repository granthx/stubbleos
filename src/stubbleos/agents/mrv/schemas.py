"""Schemas for MRV agent and evidence bundling schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EvidenceBundle(BaseModel):
    """Auditable evidence record stored in mrv_evidence."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID = Field(default_factory=uuid4)
    field_id: UUID
    evidence_type: str = "sentinel2_firms_fusion"
    model_version: str
    inputs: dict[str, Any]
    result: dict[str, Any]
    sha256: str
    captured_at: datetime
    is_synthetic: bool = True


class IndicativeImpactRecord(BaseModel):
    """Indicative impact and emissions reduction record stored in impact_records."""

    model_config = ConfigDict(extra="forbid")

    record_id: UUID = Field(default_factory=uuid4)
    field_id: UUID
    season: str = "2026_kharif"
    label: str = "indicative impact record (not registry-verified)"
    burn_avoided: bool
    area_acres: float
    est_co2e_kg_avoided: float
    method_note: str = (
        "Calculated using empirical 1.8 t/acre biomass yield factor and 1.46 kg CO2e/kg emission factor. "
        "Strictly indicative impact record (not registry-verified)."
    )
    evidence_ids: list[str] = Field(default_factory=list)
    record_sha256: str
    is_synthetic: bool = True

    @property
    def co2e_kg_avoided(self) -> float:
        return self.est_co2e_kg_avoided


ImpactEstimate = IndicativeImpactRecord


class MrvInput(BaseModel):
    """Input query to produce verified no-burn evidence and an indicative impact record."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    area_acres: float = Field(..., gt=0.0)
    season: str = "2026_kharif"
    burn_avoided: bool = True
    firms_hotspots_detected: int = 0
    satellite_cleared_confirmed: bool = True
    satellite_scene_ids: list[str] = Field(default_factory=list)
    algorithm_version: str = "stubbleos_mrv_v1.0"
    captured_at: datetime | None = None


class MrvOutput(BaseModel):
    """Output bundle from MRV agent execution."""

    model_config = ConfigDict(extra="forbid")

    evidence: EvidenceBundle
    impact: IndicativeImpactRecord
    field_id: UUID | None = None
    audit_log_id: int | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.field_id is None:
            self.field_id = self.evidence.field_id


class MrvState(BaseModel):
    """LangGraph state schema for MRV agent execution."""

    model_config = ConfigDict(extra="forbid")

    input: MrvInput
    output: MrvOutput | None = None
    status: str = "initialized"
    persisted_to_db: bool = False
