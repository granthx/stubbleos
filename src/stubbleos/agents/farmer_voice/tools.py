"""Tools for Farmer Voice agent (ASR, TTS, profile lookup, policy memory)."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from stubbleos.agents.farmer_voice.memory import FarmerMemoryStore


@tool
def transcribe_audio_mock(audio_uri: str, language: str = "punjabi") -> dict[str, Any]:
    """Mock speech-to-text transcription tool."""
    return {
        "audio_uri": audio_uri,
        "transcript": "ਮੈਨੂੰ ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ (I need a super seeder)",
        "language": language,
        "confidence": 0.96,
    }


@tool
def synthesize_speech_mock(text: str, language: str = "punjabi") -> dict[str, Any]:
    """Mock text-to-speech audio synthesis tool."""
    return {
        "text": text,
        "audio_uri": "s3://stubbleos-audio/tts_mock_001.wav",
        "duration_seconds": 3.2,
    }


@tool
def lookup_farmer_profile_tool(farmer_id: str) -> dict[str, Any]:
    """Retrieves farmer landholding size, village, and past machine bookings."""
    return {
        "farmer_id": farmer_id,
        "landholding_class": "marginal",
        "total_acres": 2.0,
        "village": "Sangrur",
        "eligible_for_subsidy": True,
        "subsidy_discount_pct": 25.0,
        "past_bookings": ["super_seeder_2025"],
    }


@tool
def search_policy_memory_tool(query: str) -> dict[str, Any]:
    """Searches CRM subsidy guidelines, baling SOPs, and fire penalty rules."""
    store = FarmerMemoryStore()
    matches = store.search_policy(query, top_k=2)
    return {
        "query": query,
        "results": [{"text": m.text, "similarity": m.similarity, "metadata": m.metadata} for m in matches],
    }


def create_farmer_voice_tools() -> list[Any]:
    return [
        transcribe_audio_mock,
        synthesize_speech_mock,
    ]


def create_extended_farmer_voice_tools() -> list[Any]:
    return [
        transcribe_audio_mock,
        synthesize_speech_mock,
        lookup_farmer_profile_tool,
        search_policy_memory_tool,
    ]


create_all_farmer_voice_tools = create_extended_farmer_voice_tools
