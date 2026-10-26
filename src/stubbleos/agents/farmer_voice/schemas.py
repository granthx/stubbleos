"""Typed contracts for Farmer Voice agent (Phase 4 skeleton, full in Phase 6)."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import Language


class FarmerVoiceTurn(BaseModel):
    """Dialogue turn in farmer communication."""

    model_config = ConfigDict(extra="forbid")

    speaker: str  # "farmer" or "agent"
    text: str
    audio_uri: str | None = None


class FarmerVoiceInput(BaseModel):
    """Input message/audio turn from a farmer."""

    model_config = ConfigDict(extra="forbid")

    farmer_id: UUID
    conversation_id: UUID = Field(default_factory=uuid4)
    language: Language = Language.PUNJABI
    inbound_text: str
    inbound_audio_uri: str | None = None


class FarmerVoiceOutput(BaseModel):
    """Agent response generated for the farmer."""

    model_config = ConfigDict(extra="forbid")

    reply_text: str
    language: Language
    detected_intent: str
    requires_human_escalation: bool = False
    action_requested: str | None = None


class FarmerVoiceState(BaseModel):
    """LangGraph state for Farmer Voice agent."""

    model_config = ConfigDict(extra="forbid")

    input: FarmerVoiceInput
    output: FarmerVoiceOutput | None = None
    turns: list[FarmerVoiceTurn] = Field(default_factory=list)
    status: str = "initialized"
