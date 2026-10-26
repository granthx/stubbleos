# Farmer Voice Agent (Phase 4 Skeleton)

## Purpose
The Farmer Voice agent conducts vernacular automated phone calls (IVR) and conversational messaging (WhatsApp/SMS) in Punjabi, Hindi, and English to record farmer machine bookings, communicate schedules, and capture consent.

## Typed Contract
- Input: `FarmerVoiceInput` (farmer ID, conversation ID, language preference, inbound message text/audio).
- Output: `FarmerVoiceOutput` (vernacular reply, detected intent, escalation flag).
- State: `FarmerVoiceState`.

## Tools
- `transcribe_audio_mock`: Simulates speech-to-text in Punjabi/Hindi.
- `synthesize_speech_mock`: Simulates text-to-speech audio rendering.
