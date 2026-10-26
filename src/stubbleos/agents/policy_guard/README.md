# Policy & Safety Guard Agent

## Purpose
The Policy & Safety Guard is a cross-cutting compliance and safety validator executed on every outbound action across StubbleOS (such as SMS/voice farmer outreach, contract offers, and machine dispatch notifications). It acts as a safety firewall that can block non-compliant operations and emit auditable policy violation events.

## Inputs
- `PolicyCheckRequest`: Contains action reference, optional farmer ID, consent purpose, communication channel, timestamp, proposed price, price bounds, message text, and payload metadata.

## Outputs
- `PolicyCheckResult`:
  - `is_allowed`: Boolean flag indicating whether the action is permitted.
  - `violations`: List of detected `PolicyViolation` records with rule ID, severity (`blocking`, `warning`, `info`), action reference, and detailed diagnostics.
  - `rule_evaluations`: Dictionary mapping each evaluated rule to its pass/fail status.

## Evaluated Rules
1. **Consent Verification (`CONSENT_REQUIRED`)**: Confirms active, unexpired farmer consent for the specified purpose (e.g. outreach) and channel via `ConsentRepository`.
2. **Price Bounds (`PRICE_OUT_OF_BOUNDS`)**: Verifies that any quoted price per tonne falls within the buyer's allowable min/max market boundaries.
3. **PII Leak Prevention (`PII_LEAK_DETECTED`)**: Scans outbound messages and metadata for unredacted Indian telephone numbers, Aadhaar numbers, or email addresses.
4. **Allowed Contact Hours (`OUTSIDE_ALLOWED_HOURS`)**: Ensures outbound farmer communication occurs only during permitted IST wall-clock hours (08:00 to 19:00 IST by default, configurable via `Settings`).

## Failure Modes & Escalation
- Missing or revoked consent: Action is blocked (`is_allowed = False`), generating a `PolicyViolationDetected` event with `severity="blocking"`.
- PII detected in text: Action is blocked immediately to protect farmer privacy.
- Contact outside allowed hours: Deferred or blocked.
- Any blocking violation can be escalated by the Orchestrator to the human approval queue (`approvals` table).
