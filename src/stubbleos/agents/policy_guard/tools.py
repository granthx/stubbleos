"""Tools for Policy & Safety Guard agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from langchain_core.tools import tool

from stubbleos.agents.policy_guard.logic import (
    check_consent,
    check_contact_hours,
    check_pii_leak,
    evaluate_policy,
)
from stubbleos.agents.policy_guard.schemas import PolicyCheckRequest, PolicyCheckResult
from stubbleos.core.config import Settings
from stubbleos.core.types import Channel, ConsentPurpose
from stubbleos.data.repositories import ConsentRepository


def create_policy_guard_tools(
    consent_repo: ConsentRepository | None = None,
    settings: Settings | None = None,
) -> list[Any]:
    """Factory to instantiate tools with repository and configuration dependencies."""

    @tool
    def validate_action(
        action_ref: str,
        message_text: str | None = None,
        proposed_price_inr_per_tonne: float | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        farmer_id_str: str | None = None,
        purpose_str: str = "outreach",
        channel_str: str = "whatsapp",
        timestamp_iso: str | None = None,
    ) -> dict[str, Any]:
        """Validates an outbound action against consent, price bounds, PII, and IST contact hours."""
        farmer_id = UUID(farmer_id_str) if farmer_id_str else None
        purpose = ConsentPurpose(purpose_str)
        channel = Channel(channel_str)
        ts = datetime.fromisoformat(timestamp_iso) if timestamp_iso else None
        bounds = (min_price, max_price) if min_price is not None and max_price is not None else None

        req = PolicyCheckRequest(
            action_ref=action_ref,
            farmer_id=farmer_id,
            purpose=purpose,
            channel=channel,
            timestamp=ts,
            proposed_price_inr_per_tonne=proposed_price_inr_per_tonne,
            price_bounds=bounds,
            message_text=message_text,
        )
        result: PolicyCheckResult = evaluate_policy(req, consent_repo=consent_repo, settings=settings)
        return result.model_dump()

    @tool
    def scan_for_pii(text: str) -> dict[str, Any]:
        """Scans free text for unredacted phone numbers, Aadhaar numbers, or emails."""
        ok, detail = check_pii_leak(text, None)
        return {"is_clean": ok, "detail": detail}

    @tool
    def check_farmer_consent(
        farmer_id_str: str,
        purpose_str: str = "outreach",
        channel_str: str = "whatsapp",
        timestamp_iso: str | None = None,
    ) -> dict[str, Any]:
        """Checks if a farmer has granted active, unexpired consent."""
        farmer_id = UUID(farmer_id_str)
        purpose = ConsentPurpose(purpose_str)
        channel = Channel(channel_str)
        ts = datetime.fromisoformat(timestamp_iso) if timestamp_iso else datetime.now()
        ok, detail = check_consent(farmer_id, purpose, channel, ts, consent_repo)
        return {"has_consent": ok, "detail": detail}

    @tool
    def check_allowed_contact_hours(timestamp_iso: str | None = None) -> dict[str, Any]:
        """Checks if current or provided time is within allowed IST contact hours."""
        ts = datetime.fromisoformat(timestamp_iso) if timestamp_iso else datetime.now()
        start = settings.contact_hours_start if settings else 8
        end = settings.contact_hours_end if settings else 19
        ok, detail = check_contact_hours(ts, start, end)
        return {"within_hours": ok, "detail": detail}

    return [validate_action, scan_for_pii, check_farmer_consent, check_allowed_contact_hours]
