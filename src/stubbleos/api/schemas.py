"""Pydantic schemas for REST API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import (
    ApprovalStatus,
    BookingStatus,
    Channel,
    ContractStatus,
    FieldState,
    ImpactRecordStatus,
    MachineStatus,
    MachineType,
    PlanStatus,
    ServiceType,
)


class FieldRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farmer_id: UUID
    district: str = "sangrur"
    village_code: str
    area_acres: float = Field(..., gt=0.0)
    center_lat: float = Field(..., ge=-90.0, le=90.0)
    center_lon: float = Field(..., ge=-180.0, le=180.0)
    crop_type: str = "paddy"


class FieldResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    farmer_id: UUID
    district: str
    village_code: str
    area_acres: float
    state: FieldState
    state_confidence: float
    burn_risk_score: float = 0.0
    center_lat: float
    center_lon: float


class MachineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    machine_type: MachineType
    district: str
    status: MachineStatus
    current_lat: float
    current_lon: float
    capacity_acres_per_day: float
    operator_name: str | None = None


class BookingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farmer_id: UUID
    field_id: UUID
    service_type: ServiceType
    machine_type: MachineType | None = None
    target_date: str
    channel: Channel = Channel.WHATSAPP


class BookingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    farmer_id: UUID
    field_id: UUID
    service_type: ServiceType
    machine_type: MachineType | None = None
    status: BookingStatus
    target_date: str
    estimated_cost_inr: float
    created_at: datetime


class PlanSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    district: str
    plan_date: str
    strategy: str
    status: PlanStatus
    fields_assigned: int
    fields_unassigned: int
    confidence: float
    routes_count: int


class ReplanTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    district: str
    reason: str
    emergency: bool = False


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: str
    subject_id: UUID
    reason: str
    status: ApprovalStatus
    confidence: float | None = None
    requested_by: str
    decided_by_role: str | None = None
    created_at: datetime


class ApprovalResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str = ""


class BiomassBidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buyer_id: UUID
    order_id: UUID = Field(default_factory=uuid4)
    price_per_tonne_inr: float = Field(..., gt=0.0)
    tonnes: float = Field(..., gt=0.0)
    delivery_term: Literal["ex_field", "cif_plant"] = "ex_field"
    moisture_max_pct: float = Field(14.0, ge=0.0, le=100.0)


class ContractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    farmer_id: UUID
    field_id: UUID
    buyer_id: UUID | None = None
    price_inr_per_tonne: float
    tonnes_agreed: float
    status: ContractStatus
    contract_sha256: str
    terms: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MrvProofResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    field_id: UUID
    season: str
    co2e_avoided_tonnes: float
    baseline_burned_prob: float
    bundle_sha256: str
    verified_status: ImpactRecordStatus
    impact_label: str = "indicative impact record (not registry-verified)"


class DistrictSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    district: str
    total_fields: int
    cleared_fields: int
    pending_residue_fields: int
    burn_incidents_detected: int
    burn_risk_index: float
    active_machines_count: int
    total_stubble_cleared_acres: float
    indicative_co2e_avoided_tonnes: float
    pending_approvals_count: int
    open_biomass_orders_count: int
