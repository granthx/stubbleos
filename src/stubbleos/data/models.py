"""SQLAlchemy 2.0 ORM models.

Two Postgres schemas enforce the PII boundary (ADR-0003):
  * ``core``: analytics-safe. Farmers appear only as pseudonymous rows; no names, phones or message bodies.
  * ``pii``: identities and raw message text, linked to ``core`` by id. Erasure = null the PII columns
    and set ``erased_at``; analytics rows remain valid.
"""

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, ClassVar

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from stubbleos.core.types import (
    ApprovalStatus,
    BookingStatus,
    BuyerType,
    Channel,
    ConsentPurpose,
    ContractStatus,
    ConversationStatus,
    FieldState,
    ImpactRecordStatus,
    LandholdingClass,
    Language,
    MachineStatus,
    MachineType,
    OrderStatus,
    PlanStatus,
    RouteType,
    ServiceType,
)

CORE = "core"
PII = "pii"
IMPACT_LABEL = "indicative impact record (not registry-verified)"

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONType,
        uuid.UUID: Uuid,
    }


def core_args(*items: Any) -> tuple[Any, ...]:
    return (*items, {"schema": CORE})


def pii_args(*items: Any) -> tuple[Any, ...]:
    return (*items, {"schema": PII})


def enum_col(enum_cls: type[Enum], name: str) -> SAEnum:
    """Portable string enum with a named CHECK constraint (no native PG enum types to migrate)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def created_at_col() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())


def fk(
    target: str, *, nullable: bool = False, ondelete: str | None = None, index: bool = True
) -> Mapped[Any]:
    return mapped_column(ForeignKey(target, ondelete=ondelete), nullable=nullable, index=index)


# =============================================================================== core: actors


class Farmer(Base):
    __tablename__ = "farmers"
    __table_args__ = core_args(
        CheckConstraint("trust_score >= 0 AND trust_score <= 1", name="trust_score_range"),
        CheckConstraint("total_area_acres >= 0", name="area_nonneg"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    pseudonym: Mapped[str] = mapped_column(String(48), unique=True)
    district: Mapped[str] = mapped_column(String(64), index=True)
    village_code: Mapped[str | None] = mapped_column(String(32))
    landholding_class: Mapped[LandholdingClass] = mapped_column(
        enum_col(LandholdingClass, "landholding_class")
    )
    total_area_acres: Mapped[float] = mapped_column(Float)
    income_band: Mapped[str | None] = mapped_column(String(16))
    trust_score: Mapped[float] = mapped_column(Float, default=0.5)
    preferred_language: Mapped[Language] = mapped_column(
        enum_col(Language, "language"), default=Language.PUNJABI
    )
    created_at: Mapped[datetime] = created_at_col()


class Operator(Base):
    __tablename__ = "operators"
    __table_args__ = core_args()
    id: Mapped[uuid.UUID] = uuid_pk()
    pseudonym: Mapped[str] = mapped_column(String(48), unique=True)
    district: Mapped[str] = mapped_column(String(64), index=True)
    certified_machine_types: Mapped[list[str]] = mapped_column(JSONType, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_col()


class Machine(Base):
    __tablename__ = "machines"
    __table_args__ = core_args(
        CheckConstraint("capacity_acres_per_hour > 0", name="capacity_positive"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    machine_type: Mapped[MachineType] = mapped_column(enum_col(MachineType, "machine_type"))
    owner_farmer_id: Mapped[uuid.UUID | None] = fk("core.farmers.id", nullable=True)
    owner_org: Mapped[str | None] = mapped_column(String(128))
    operator_id: Mapped[uuid.UUID | None] = fk("core.operators.id", nullable=True)
    district: Mapped[str] = mapped_column(String(64), index=True)
    home_location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326))
    capacity_acres_per_hour: Mapped[float] = mapped_column(Float)
    hourly_cost_inr: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[MachineStatus] = mapped_column(
        enum_col(MachineStatus, "machine_status"), default=MachineStatus.AVAILABLE
    )
    created_at: Mapped[datetime] = created_at_col()


class FieldRow(Base):
    __tablename__ = "fields"
    __table_args__ = core_args(
        CheckConstraint("area_acres > 0", name="area_positive"),
        CheckConstraint("state_confidence >= 0 AND state_confidence <= 1", name="confidence_range"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    farmer_id: Mapped[uuid.UUID] = fk("core.farmers.id")
    district: Mapped[str] = mapped_column(String(64), index=True)
    geom: Mapped[Any] = mapped_column(Geometry("POLYGON", srid=4326))
    area_acres: Mapped[float] = mapped_column(Float)
    crop: Mapped[str] = mapped_column(String(32), default="paddy")
    harvest_date: Mapped[date | None] = mapped_column()
    sowing_deadline: Mapped[date | None] = mapped_column()
    residue_tonnes_est: Mapped[float | None] = mapped_column(Float)
    state: Mapped[FieldState] = mapped_column(
        enum_col(FieldState, "field_state"),
        default=FieldState.NOT_HARVESTED,
        server_default=FieldState.NOT_HARVESTED.value,
        index=True,
    )
    state_confidence: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    state_updated_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at_col()


class Buyer(Base):
    __tablename__ = "buyers"
    __table_args__ = core_args()
    id: Mapped[uuid.UUID] = uuid_pk()
    org_name: Mapped[str] = mapped_column(String(128))
    buyer_type: Mapped[BuyerType] = mapped_column(enum_col(BuyerType, "buyer_type"))
    district: Mapped[str] = mapped_column(String(64), index=True)
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326))
    max_moisture_pct: Mapped[float] = mapped_column(Float, default=15.0)
    created_at: Mapped[datetime] = created_at_col()


# =============================================================================== core: market


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = core_args(
        CheckConstraint("tonnes_required > 0", name="tonnes_positive"),
        CheckConstraint("tonnes_filled >= 0", name="filled_nonneg"),
        CheckConstraint("window_end >= window_start", name="window_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    buyer_id: Mapped[uuid.UUID] = fk("core.buyers.id")
    tonnes_required: Mapped[float] = mapped_column(Float)
    tonnes_filled: Mapped[float] = mapped_column(Float, default=0.0)
    price_inr_per_tonne: Mapped[float] = mapped_column(Float)
    max_moisture_pct: Mapped[float] = mapped_column(Float)
    window_start: Mapped[date] = mapped_column()
    window_end: Mapped[date] = mapped_column()
    status: Mapped[OrderStatus] = mapped_column(
        enum_col(OrderStatus, "order_status"), default=OrderStatus.OPEN
    )
    created_at: Mapped[datetime] = created_at_col()


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = core_args(
        UniqueConstraint("district", "plan_date", "strategy", "version", name="uq_plans_identity"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    district: Mapped[str] = mapped_column(String(64), index=True)
    plan_date: Mapped[date] = mapped_column()
    strategy: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[PlanStatus] = mapped_column(enum_col(PlanStatus, "plan_status"), default=PlanStatus.DRAFT)
    parent_plan_id: Mapped[uuid.UUID | None] = fk("core.plans.id", nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    objective_value: Mapped[float | None] = mapped_column(Float)
    solver_status: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = created_at_col()


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = core_args(
        CheckConstraint("scheduled_end > scheduled_start", name="schedule_valid"),
        Index("ix_bookings_field_status", "field_id", "status"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    field_id: Mapped[uuid.UUID] = fk("core.fields.id", index=False)
    machine_id: Mapped[uuid.UUID | None] = fk("core.machines.id", nullable=True)
    plan_id: Mapped[uuid.UUID | None] = fk("core.plans.id", nullable=True)
    service_type: Mapped[ServiceType] = mapped_column(enum_col(ServiceType, "service_type"))
    scheduled_start: Mapped[datetime] = mapped_column()
    scheduled_end: Mapped[datetime] = mapped_column()
    status: Mapped[BookingStatus] = mapped_column(
        enum_col(BookingStatus, "booking_status"), default=BookingStatus.PROPOSED
    )
    price_inr: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = created_at_col()


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = core_args()
    id: Mapped[uuid.UUID] = uuid_pk()
    plan_id: Mapped[uuid.UUID] = fk("core.plans.id")
    route_type: Mapped[RouteType] = mapped_column(enum_col(RouteType, "route_type"))
    vehicle_ref: Mapped[str] = mapped_column(String(64))
    stops: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    duration_min: Mapped[float] = mapped_column(Float, default=0.0)
    cost_inr: Mapped[float] = mapped_column(Float, default=0.0)
    co2_kg: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = created_at_col()


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = core_args(
        CheckConstraint("price_inr_per_tonne > 0", name="price_positive"),
        CheckConstraint("tonnes_agreed > 0", name="tonnes_positive"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID | None] = fk("core.orders.id", nullable=True)
    field_id: Mapped[uuid.UUID] = fk("core.fields.id")
    farmer_id: Mapped[uuid.UUID] = fk("core.farmers.id")
    buyer_id: Mapped[uuid.UUID | None] = fk("core.buyers.id", nullable=True)
    terms: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    price_inr_per_tonne: Mapped[float] = mapped_column(Float)
    tonnes_agreed: Mapped[float] = mapped_column(Float)
    status: Mapped[ContractStatus] = mapped_column(
        enum_col(ContractStatus, "contract_status"), default=ContractStatus.DRAFT
    )
    pdf_uri: Mapped[str | None] = mapped_column(Text)
    contract_sha256: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at_col()


# =============================================================================== core: interaction


class Conversation(Base):
    """Metadata only. Message text lives in ``pii.conversation_messages``."""

    __tablename__ = "conversations"
    __table_args__ = core_args()
    id: Mapped[uuid.UUID] = uuid_pk()
    farmer_id: Mapped[uuid.UUID] = fk("core.farmers.id")
    channel: Mapped[Channel] = mapped_column(enum_col(Channel, "channel"))
    language: Mapped[Language] = mapped_column(enum_col(Language, "language"))
    status: Mapped[ConversationStatus] = mapped_column(
        enum_col(ConversationStatus, "conversation_status"), default=ConversationStatus.OPEN
    )
    outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # structured, PII-free
    started_at: Mapped[datetime] = created_at_col()
    ended_at: Mapped[datetime | None] = mapped_column()


class Consent(Base):
    """Append-only consent ledger. Revocation is a new row with granted=False; the latest wins."""

    __tablename__ = "consents"
    __table_args__ = core_args(Index("ix_consents_lookup", "farmer_id", "purpose", "channel"))
    id: Mapped[uuid.UUID] = uuid_pk()
    farmer_id: Mapped[uuid.UUID] = fk("core.farmers.id", index=False)
    purpose: Mapped[ConsentPurpose] = mapped_column(enum_col(ConsentPurpose, "consent_purpose"))
    channel: Mapped[Channel] = mapped_column(enum_col(Channel, "channel"))
    granted: Mapped[bool] = mapped_column(Boolean)
    language: Mapped[Language] = mapped_column(enum_col(Language, "language"))
    recorded_at: Mapped[datetime] = mapped_column()
    expires_at: Mapped[datetime | None] = mapped_column()
    evidence_ref: Mapped[str | None] = mapped_column(Text)  # e.g. hash of the consent message
    recorded_by: Mapped[str] = mapped_column(String(64))


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = core_args(
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_range"
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(String(48), index=True)
    subject_type: Mapped[str] = mapped_column(String(48))
    subject_id: Mapped[uuid.UUID] = mapped_column()
    status: Mapped[ApprovalStatus] = mapped_column(
        enum_col(ApprovalStatus, "approval_status"), default=ApprovalStatus.PENDING, index=True
    )
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    requested_by: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    decided_by_role: Mapped[str | None] = mapped_column(String(48))
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at_col()


# =============================================================================== core: audit, MRV


class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = core_args(Index("ix_agent_events_corr_ts", "correlation_id", "ts"))
    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(48))
    ts: Mapped[datetime] = mapped_column(index=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column()
    district: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)


class MrvEvidence(Base):
    __tablename__ = "mrv_evidence"
    __table_args__ = core_args()
    id: Mapped[uuid.UUID] = uuid_pk()
    field_id: Mapped[uuid.UUID] = fk("core.fields.id")
    evidence_type: Mapped[str] = mapped_column(String(32))  # firms | sentinel2 | simulation | ...
    model_version: Mapped[str] = mapped_column(String(64))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONType)
    result: Mapped[dict[str, Any]] = mapped_column(JSONType)
    sha256: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column()
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_col()


class ImpactRecord(Base):
    """Indicative only. The CHECK constraint makes it impossible to store an unlabeled record."""

    __tablename__ = "impact_records"
    __table_args__ = core_args(
        UniqueConstraint("field_id", "season", name="uq_impact_records_field_season"),
        CheckConstraint("label LIKE '%not registry-verified%'", name="label_disclaimer"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    field_id: Mapped[uuid.UUID] = fk("core.fields.id", index=False)
    season: Mapped[str] = mapped_column(String(16))
    status: Mapped[ImpactRecordStatus] = mapped_column(
        enum_col(ImpactRecordStatus, "impact_status"), default=ImpactRecordStatus.INDICATIVE
    )
    label: Mapped[str] = mapped_column(String(96), default=IMPACT_LABEL, server_default=IMPACT_LABEL)
    burn_avoided: Mapped[bool] = mapped_column(Boolean)
    area_acres: Mapped[float] = mapped_column(Float)
    est_co2e_kg_avoided: Mapped[float | None] = mapped_column(Float)
    method_note: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list[str]] = mapped_column(JSONType, default=list)
    record_sha256: Mapped[str] = mapped_column(String(64))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_col()


class AuditLog(Base):
    """Hash-chained, append-only (DB trigger blocks UPDATE/DELETE/TRUNCATE; see migration 0001)."""

    __tablename__ = "audit_log"
    __table_args__ = core_args()
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    ts: Mapped[datetime] = mapped_column(index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)


# =============================================================================== pii schema


class FarmerIdentity(Base):
    __tablename__ = "farmer_identities"
    __table_args__ = pii_args()
    farmer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.farmers.id", ondelete="CASCADE"), primary_key=True
    )
    full_name: Mapped[str | None] = mapped_column(Text)
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    village_name: Mapped[str | None] = mapped_column(Text)
    erased_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at_col()


class OperatorIdentity(Base):
    __tablename__ = "operator_identities"
    __table_args__ = pii_args()
    operator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.operators.id", ondelete="CASCADE"), primary_key=True
    )
    full_name: Mapped[str | None] = mapped_column(Text)
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    erased_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at_col()


class BuyerContact(Base):
    __tablename__ = "buyer_contacts"
    __table_args__ = pii_args()
    id: Mapped[uuid.UUID] = uuid_pk()
    buyer_id: Mapped[uuid.UUID] = fk("core.buyers.id", ondelete="CASCADE")
    contact_name: Mapped[str | None] = mapped_column(Text)
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = pii_args()
    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = fk("core.conversations.id", ondelete="CASCADE")
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


CORE_TABLES_REQUIRED = frozenset(
    {
        "farmers", "fields", "machines", "operators", "buyers", "orders", "bookings", "routes",
        "contracts", "conversations", "agent_events", "plans", "mrv_evidence", "impact_records",
        "approvals", "consents", "audit_log",
    }
)  # fmt: skip
