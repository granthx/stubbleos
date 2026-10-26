"""Domain entities and state representations for the district simulation."""

from __future__ import annotations

import math
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import (
    BuyerType,
    FieldState,
    LandholdingClass,
    Language,
    MachineStatus,
    MachineType,
)


class SimulatedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    farmer_id: UUID
    area_acres: float
    residue_tonnes_est: float
    harvest_day: float
    sowing_deadline_day: float
    state: FieldState = FieldState.NOT_HARVESTED
    cleared_at_day: float | None = None
    burned_at_day: float | None = None
    center_lat: float
    center_lon: float
    polygon_coords: list[tuple[float, float]]
    assigned_machine_id: UUID | None = None
    service_in_progress: bool = False
    is_synthetic: bool = True

    @property
    def is_cleared(self) -> bool:
        return self.state == FieldState.CLEARED

    @property
    def is_burned(self) -> bool:
        return self.state == FieldState.BURN_DETECTED

    @property
    def is_harvested(self) -> bool:
        return self.state != FieldState.NOT_HARVESTED


class SimulatedFarmer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farmer_id: UUID
    pseudonym: str
    landholding_class: LandholdingClass
    total_area_acres: float
    trust_score: float
    income_band: str  # "low", "medium", "high"
    preferred_language: Language = Language.PUNJABI
    field_ids: list[UUID] = Field(default_factory=list)
    net_income_inr: float = 0.0
    burn_cost_penalty_inr: float = 0.0
    machine_fees_paid_inr: float = 0.0
    straw_revenue_earned_inr: float = 0.0
    is_synthetic: bool = True


class SimulatedMachine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    machine_id: UUID
    machine_type: MachineType
    capacity_acres_per_hour: float
    hourly_cost_inr: float
    status: MachineStatus = MachineStatus.AVAILABLE
    current_lat: float
    current_lon: float
    home_lat: float
    home_lon: float
    current_field_id: UUID | None = None
    operating_hours: float = 0.0
    idle_hours: float = 0.0
    breakdown_hours: float = 0.0
    transit_hours: float = 0.0
    acres_worked: float = 0.0
    is_synthetic: bool = True


class SimulatedOperator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_id: UUID
    pseudonym: str
    certified_machine_types: list[MachineType]
    is_active: bool = True
    is_synthetic: bool = True


class SimulatedBuyer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buyer_id: UUID
    org_name: str
    buyer_type: BuyerType
    lat: float
    lon: float
    tonnes_required: float
    tonnes_filled: float = 0.0
    price_inr_per_tonne: float
    max_moisture_pct: float
    is_synthetic: bool = True

    @property
    def remaining_demand(self) -> float:
        return max(0.0, self.tonnes_required - self.tonnes_filled)


class SimulatedTruck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    truck_id: UUID
    capacity_tonnes: float = 10.0
    cost_per_km_inr: float = 45.0
    total_km_travelled: float = 0.0
    total_tonnes_hauled: float = 0.0
    is_available: bool = True
    is_synthetic: bool = True


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km with road winding factor (1.3x)."""
    r = 6371.0  # Earth radius km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    road_winding_factor = 1.3
    return r * c * road_winding_factor


class DistrictState(BaseModel):
    """Encapsulates the complete state of a simulated agricultural district."""

    model_config = ConfigDict(extra="forbid")

    district_name: str
    farmers: list[SimulatedFarmer]
    fields: list[SimulatedField]
    machines: list[SimulatedMachine]
    operators: list[SimulatedOperator]
    buyers: list[SimulatedBuyer]
    trucks: list[SimulatedTruck]
    is_synthetic: bool = True

    _fields_by_id: dict[UUID, SimulatedField] | None = None
    _farmers_by_id: dict[UUID, SimulatedFarmer] | None = None
    _machines_by_id: dict[UUID, SimulatedMachine] | None = None
    _buyers_by_id: dict[UUID, SimulatedBuyer] | None = None

    def get_field(self, field_id: UUID) -> SimulatedField:
        if self._fields_by_id is None:
            self._fields_by_id = {f.field_id: f for f in self.fields}
        return self._fields_by_id[field_id]

    def get_farmer(self, farmer_id: UUID) -> SimulatedFarmer:
        if self._farmers_by_id is None:
            self._farmers_by_id = {f.farmer_id: f for f in self.farmers}
        return self._farmers_by_id[farmer_id]

    def get_machine(self, machine_id: UUID) -> SimulatedMachine:
        if self._machines_by_id is None:
            self._machines_by_id = {m.machine_id: m for m in self.machines}
        return self._machines_by_id[machine_id]

    @property
    def total_acres(self) -> float:
        return sum(f.area_acres for f in self.fields)

    @property
    def cleared_acres(self) -> float:
        return sum(f.area_acres for f in self.fields if f.state == FieldState.CLEARED)

    @property
    def burned_acres(self) -> float:
        return sum(f.area_acres for f in self.fields if f.state == FieldState.BURN_DETECTED)

    @property
    def unharvested_acres(self) -> float:
        return sum(f.area_acres for f in self.fields if f.state == FieldState.NOT_HARVESTED)

    @property
    def total_straw_tonnes(self) -> float:
        return sum(f.residue_tonnes_est for f in self.fields)

    @property
    def delivered_straw_tonnes(self) -> float:
        return sum(b.tonnes_filled for b in self.buyers)

    @property
    def burned_straw_tonnes(self) -> float:
        return sum(f.residue_tonnes_est for f in self.fields if f.state == FieldState.BURN_DETECTED)
