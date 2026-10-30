# ADR 0013: Vernacular Voice Dialogue and Channel Layer

**Status:** accepted (Phase 6)  
**Date:** 2026-10-30  
**Context:** StubbleOS Phase 6 (Farmer Voice & Vernacular Negotiation)

## Context

Smallholder and marginal farmers across Punjab and Haryana predominantly speak Punjabi and Hindi, with substantial usage of Gurmukhi script, Devanagari script, Romanized transliterations (Hinglish/Roman Punjabi), and automated voice phone calls (IVR). A pure web dashboard or English-only interface excludes the very farmers who are under the greatest time pressure to clear paddy residue before wheat sowing deadlines.

Furthermore:
1. Outreach must respect privacy and quiet hours (21:00 to 07:00 IST) to prevent intrusive spam.
2. The Digital Personal Data Protection (DPDP) Act mandates explicit consent prior to outbound notifications.
3. Desperate farmers facing impending deadlines frequently state intentions to burn stubble; the system must identify these threats immediately, provide empathetic de-escalation, and alert human operators with critical priority.

## Decision

1. **Multilingual NLP Engine**:
   - Classifies intents (`book_machine`, `query_price`, `check_schedule_status`, `confirm_booking`, `cancel_booking`, `threat_burn`, `give_consent`).
   - Extracts agricultural entities (acres, villages, machine types, preferred dates) with multi-turn slot filling.
   - Detects script and falls back gracefully to deterministic templates registered in `PromptRegistry` if LLM service is degraded or offline.

2. **Channel Adapters**:
   - `WhatsAppChannel`: Handles Meta WhatsApp Cloud / Business API payloads with interactive buttons and templates.
   - `IVRChannel`: Telephony voice adapter supporting DTMF keypad tones, automated call sessions, and synthesized voice prompts.
   - `MockChannel`: Deterministic in-memory channel for tests and simulations.

3. **PII Isolation & Consent Enforcement**:
   - `ChannelRouter` queries `ConsentRepository.has_valid_consent` before any outbound dispatch.
   - Quiet hours policy delays non-urgent notifications between 21:00 and 07:00 IST.
   - All inbound/outbound event bus logs are automatically scrubbed by `PIIRedactor`, storing raw message text exclusively in `pii.conversation_messages`.

4. **Burn Threat Escalation Protocol**:
   - Detects burning threats (e.g. "ਅੱਗ ਲਾ ਦੇਵਾਂਗਾ", "ਆਗ ਲਗਾ ਦੂੰਗਾ", "will burn tomorrow").
   - Immediately sets `requires_human_escalation=True` and emits a high-priority `HumanEscalationTriggered` event to the approval queue.

## Consequences

- Farmers can book machines via voice calls or WhatsApp in their native language.
- Zero PII leaks into analytics or event bus streams.
- Critical burn threats are intercepted and surfaced to district coordinators within seconds.

