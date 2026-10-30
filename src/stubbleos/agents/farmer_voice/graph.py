"""LangGraph workflow for Farmer Voice agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.farmer_voice.logic import process_voice_interaction
from stubbleos.agents.farmer_voice.schemas import (
    FarmerVoiceState,
    FarmerVoiceTurn,
)
from stubbleos.core.types import Channel
from stubbleos.llm.base import LLMClient


def build_farmer_voice_graph(
    llm: LLMClient | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles Farmer Voice LangGraph workflow."""

    async def converse_node(state: FarmerVoiceState) -> dict[str, Any]:
        output = await process_voice_interaction(
            state.input,
            current_slots=state.slots,
            llm=llm,
        )

        # Update turns history
        turns = list(state.turns)
        if state.input.inbound_text:
            turns.append(
                FarmerVoiceTurn(
                    speaker="farmer",
                    text=state.input.inbound_text,
                    audio_uri=state.input.inbound_audio_uri,
                    timestamp=state.input.timestamp,
                )
            )

        # Synthesize audio if on voice channel
        audio_uri = None
        if state.input.channel == Channel.VOICE:
            audio_uri = f"s3://stubbleos-audio/tts_{state.input.conversation_id}.wav"
            output.audio_uri = audio_uri

        turns.append(
            FarmerVoiceTurn(
                speaker="agent",
                text=output.reply_text,
                audio_uri=audio_uri,
                timestamp=state.input.timestamp,
            )
        )

        return {
            "output": output,
            "turns": turns,
            "slots": output.slots or state.slots,
            "status": "completed",
        }

    builder = StateGraph(FarmerVoiceState)
    builder.add_node("converse", converse_node)
    builder.add_edge(START, "converse")
    builder.add_edge("converse", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
