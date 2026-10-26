"""Shared domain vocabulary: base models, scalar aliases and enums.

Enums defined here are the single source of truth: ORM models, event payloads,
agents and the simulator all import them from this module.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
Latitude = Annotated[float, Field(ge=-90.0, le=90.0)]
Longitude = Annotated[float, Field(ge=-180.0, le=180.0)]


class StrictModel(BaseModel):
    """Base for all typed messages: unknown fields are errors, assignments are validated."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FrozenModel(StrictModel):
    """Immutable variant, hashable when all fields are hashable."""

    model_config = ConfigDict(frozen=True)


class GeoPoint(FrozenModel):
    lat: Latitude
    lon: Longitude


class FieldState(StrEnum):
    NOT_HARVESTED = "not_harvested"
    HARVESTED_RESIDUE_PRESENT = "harvested_residue_present"
    CLEARED = "cleared"
    BURN_DETECTED = "burn_detected"


class Language(StrEnum):
    PUNJABI = "pa"
    HINDI = "hi"
    ENGLISH = "en"


class Channel(StrEnum):
    WHATSAPP = "whatsapp"
    VOICE = "voice"
    MOCK = "mock"


class MachineType(StrEnum):
    HAPPY_SEEDER = "happy_seeder"
    SUPER_SEEDER = "super_seeder"
    BALER = "baler"
    RAKE = "rake"


class MachineStatus(StrEnum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    BROKEN = "broken"
    MAINTENANCE = "maintenance"


class ServiceType(StrEnum):
    IN_SITU_SOWING = "in_situ_sowing"
    BALING = "baling"
    RAKING = "raking"
    TRANSPORT = "transport"


class LandholdingClass(StrEnum):
    """Indian agricultural-census style size classes (hectares in comments)."""

    MARGINAL = "marginal"  # < 1
    SMALL = "small"  # 1 - 2
    SEMI_MEDIUM = "semi_medium"  # 2 - 4
    MEDIUM = "medium"  # 4 - 10
    LARGE = "large"  # > 10


class BuyerType(StrEnum):
    BIOMASS_PLANT = "biomass_plant"
    CBG_PLANT = "cbg_plant"
    PAPER_MILL = "paper_mill"
    BOARD_MILL = "board_mill"
    OTHER = "other"


class OrderStatus(StrEnum):
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BookingStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class RouteType(StrEnum):
    MACHINE = "machine"
    TRUCK = "truck"


class ContractStatus(StrEnum):
    DRAFT = "draft"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class ConversationStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ESCALATED = "escalated"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ImpactRecordStatus(StrEnum):
    INDICATIVE = "indicative"
    FLAGGED = "flagged"
    WITHDRAWN = "withdrawn"


class ConsentPurpose(StrEnum):
    OUTREACH = "outreach"
    DATA_PROCESSING = "data_processing"
    CONTRACT = "contract"
    MRV_SHARING = "mrv_sharing"


class ReplanReason(StrEnum):
    DAILY = "daily"
    RAIN_FORECAST_CHANGE = "rain_forecast_change"
    MACHINE_BREAKDOWN = "machine_breakdown"
    BURN_DETECTED = "burn_detected"
    BUYER_DEMAND_CHANGE = "buyer_demand_change"
    MANUAL = "manual"


class AgentName(StrEnum):
    ORCHESTRATOR = "orchestrator"
    FIELD_MONITOR = "field_monitor"
    WEATHER_WINDOW = "weather_window"
    FARMER_VOICE = "farmer_voice"
    MACHINE_SCHEDULER = "machine_scheduler"
    LOGISTICS = "logistics"
    BUYER_DEMAND = "buyer_demand"
    PRICING_NEGOTIATION = "pricing_negotiation"
    MRV = "mrv"
    POLICY_GUARD = "policy_guard"
    SIMULATOR = "simulator"
    SYSTEM = "system"
