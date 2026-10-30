"""Typed contracts for Farmer Voice agent."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import Channel, Language, MachineType


class FarmerVoiceSlotState(BaseModel):
    """Accumulated slot values in multi-turn booking conversations."""

    model_config = ConfigDict(extra="forbid")

    area_acres: float | None = None
    village: str | None = None
    machine_type: MachineType | None = None
    target_date: str | None = None
    crop_type: str | None = "paddy"
    is_confirmed: bool = False


class FarmerVoiceBookingDraft(BaseModel):
    """Structured booking intent ready for reservation upon farmer confirmation."""

    model_config = ConfigDict(extra="forbid")

    area_acres: float
    village: str
    machine_type: MachineType
    target_date: str
    crop_type: str = "paddy"
    estimated_rate_inr: float | None = None


class FarmerVoiceTurn(BaseModel):
    """Dialogue turn in farmer communication."""

    model_config = ConfigDict(extra="forbid")

    speaker: str  # "farmer" or "agent"
    text: str
    audio_uri: str | None = None
    timestamp: datetime | None = None


class FarmerVoiceInput(BaseModel):
    """Input message/audio turn from a farmer."""

    model_config = ConfigDict(extra="forbid")

    farmer_id: UUID
    conversation_id: UUID = Field(default_factory=uuid4)
    language: Language = Language.PUNJABI
    inbound_text: str = ""
    inbound_audio_uri: str | None = None
    channel: Channel = Channel.WHATSAPP
    timestamp: datetime | None = None


class FarmerVoiceOutput(BaseModel):
    """Agent response generated for the farmer."""

    model_config = ConfigDict(extra="forbid")

    reply_text: str
    language: Language
    detected_intent: str
    confidence: float = 1.0
    requires_human_escalation: bool = False
    escalation_reason: str | None = None
    action_requested: str | None = None
    booking_draft: FarmerVoiceBookingDraft | None = None
    audio_uri: str | None = None
    slots: FarmerVoiceSlotState | None = None


class FarmerVoiceState(BaseModel):
    """LangGraph state for Farmer Voice agent."""

    model_config = ConfigDict(extra="forbid")

    input: FarmerVoiceInput
    output: FarmerVoiceOutput | None = None
    turns: list[FarmerVoiceTurn] = Field(default_factory=list)
    slots: FarmerVoiceSlotState = Field(default_factory=FarmerVoiceSlotState)
    status: str = "initialized"
    context_docs: list[str] = Field(default_factory=list)
