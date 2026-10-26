"""Mock tools for Farmer Voice agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


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


def create_farmer_voice_tools() -> list[Any]:
    return [transcribe_audio_mock, synthesize_speech_mock]
