"""Pure policy evaluation engine for Policy & Safety Guard."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from stubbleos.agents.policy_guard.schemas import (
    PolicyCheckRequest,
    PolicyCheckResult,
    PolicyViolation,
)
from stubbleos.core.clock import IST, as_utc
from stubbleos.core.config import Settings, get_settings
from stubbleos.core.events import PolicyViolationDetected
from stubbleos.core.types import Channel, ConsentPurpose
from stubbleos.data.repositories import ConsentRepository

PHONE_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:\+?91[\s-]?)?[6-9]\d{9}(?![A-Za-z0-9])")
AADHAAR_PATTERN = re.compile(r"(?<![A-Za-z0-9])\d{4}\s\d{4}\s\d{4}(?![A-Za-z0-9])")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


def check_consent(
    farmer_id: UUID | None,
    purpose: ConsentPurpose,
    channel: Channel,
    at: datetime,
    consent_repo: ConsentRepository | None,
) -> tuple[bool, str | None]:
    """Check if farmer has valid active consent for purpose and channel."""
    if farmer_id is None:
        return True, None
    if consent_repo is None:
        # If no repository is provided, we cannot verify consent
        return False, f"Cannot verify consent for farmer {farmer_id}: repository unavailable."

    has_consent = consent_repo.has_valid_consent(farmer_id, purpose, channel, at)
    if not has_consent:
        return (
            False,
            f"Farmer {farmer_id} has not granted valid consent for {purpose.value} on {channel.value}.",
        )
    return True, None


def check_price_bounds(
    price: float | None,
    bounds: tuple[float, float] | None,
) -> tuple[bool, str | None]:
    """Check if proposed price falls within allowable market bounds."""
    if price is None or bounds is None:
        return True, None
    min_price, max_price = bounds
    if price < min_price or price > max_price:
        return (
            False,
            f"Price {price:.2f} INR/tonne is outside allowable bounds [{min_price:.2f}, {max_price:.2f}].",
        )
    return True, None


def check_pii_leak(
    text: str | None,
    payload: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    """Scan message text and payload for unredacted PII (phones, Aadhaar, email)."""
    target_str = (text or "") + " " + json.dumps(payload or {}, default=str)

    if PHONE_PATTERN.search(target_str):
        return False, "PII leak detected: unredacted phone number found in outbound payload."
    if AADHAAR_PATTERN.search(target_str):
        return False, "PII leak detected: unredacted Aadhaar number found in outbound payload."
    if EMAIL_PATTERN.search(target_str):
        return False, "PII leak detected: unredacted email address found in outbound payload."

    return True, None


def check_contact_hours(
    timestamp: datetime,
    start_hour: int,
    end_hour: int,
) -> tuple[bool, str | None]:
    """Check if timestamp falls within allowed contact window in Indian Standard Time (IST)."""
    ist_dt = as_utc(timestamp).astimezone(IST)
    current_hour = ist_dt.hour
    if current_hour < start_hour or current_hour >= end_hour:
        return (
            False,
            f"Contact attempt at {ist_dt.strftime('%H:%M')} IST is outside allowed window ({start_hour:02d}:00 to {end_hour:02d}:00 IST).",
        )
    return True, None


def evaluate_policy(
    request: PolicyCheckRequest,
    *,
    consent_repo: ConsentRepository | None = None,
    settings: Settings | None = None,
) -> PolicyCheckResult:
    """Evaluates all cross-cutting policy rules on an outbound action."""
    cfg = settings or get_settings()
    ts = request.timestamp or datetime.now(IST)

    violations: list[PolicyViolation] = []
    evaluations: dict[str, bool] = {}

    # 1. Consent rule
    consent_ok, consent_detail = check_consent(
        farmer_id=request.farmer_id,
        purpose=request.purpose,
        channel=request.channel,
        at=ts,
        consent_repo=consent_repo,
    )
    evaluations["consent_obtained"] = consent_ok
    if not consent_ok and consent_detail is not None:
        violations.append(
            PolicyViolation(
                rule_id="CONSENT_REQUIRED",
                severity="blocking",
                action_ref=request.action_ref,
                detail=consent_detail,
            )
        )

    # 2. Price bounds rule
    price_ok, price_detail = check_price_bounds(
        price=request.proposed_price_inr_per_tonne,
        bounds=request.price_bounds,
    )
    evaluations["price_bounds"] = price_ok
    if not price_ok and price_detail is not None:
        violations.append(
            PolicyViolation(
                rule_id="PRICE_OUT_OF_BOUNDS",
                severity="blocking",
                action_ref=request.action_ref,
                detail=price_detail,
            )
        )

    # 3. PII leak prevention
    pii_ok, pii_detail = check_pii_leak(
        text=request.message_text,
        payload=request.payload,
    )
    evaluations["no_pii_leaks"] = pii_ok
    if not pii_ok and pii_detail is not None:
        violations.append(
            PolicyViolation(
                rule_id="PII_LEAK_DETECTED",
                severity="blocking",
                action_ref=request.action_ref,
                detail=pii_detail,
            )
        )

    # 4. Contact hours in IST (applies when contacting a farmer or sending outbound messages)
    if request.farmer_id is not None or request.message_text is not None:
        hours_ok, hours_detail = check_contact_hours(
            timestamp=ts,
            start_hour=cfg.contact_hours_start,
            end_hour=cfg.contact_hours_end,
        )
    else:
        hours_ok, hours_detail = True, None
    evaluations["contact_hours_ist"] = hours_ok
    if not hours_ok and hours_detail is not None:
        violations.append(
            PolicyViolation(
                rule_id="OUTSIDE_ALLOWED_HOURS",
                severity="blocking",
                action_ref=request.action_ref,
                detail=hours_detail,
            )
        )

    is_allowed = not any(v.severity == "blocking" for v in violations)
    return PolicyCheckResult(
        is_allowed=is_allowed,
        action_ref=request.action_ref,
        violations=violations,
        rule_evaluations=evaluations,
    )


def build_violation_events(result: PolicyCheckResult) -> list[PolicyViolationDetected]:
    """Helper to construct typed Event payloads from policy violations."""
    return [
        PolicyViolationDetected(
            rule_id=v.rule_id,
            severity=v.severity,
            action_ref=v.action_ref,
            detail=v.detail,
        )
        for v in result.violations
    ]
