"""PII handling: log redaction and keyed pseudonymization.

Redaction is a safety net for logs, not a licence to log PII. Agents should never pass
raw names, phone numbers or message bodies to a logger in the first place.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

# Indian mobile: optional +91 / 91 / 0091 prefix, then 10 digits starting 6-9.
_PHONE_RE = re.compile(r"(?<!\d)(?:(?:\+|00)?91[\s-]?)?[6-9]\d{9}(?!\d)")
# Aadhaar-like: 12 digits (optionally grouped by 4) not starting with 0/1.
_AADHAAR_RE = re.compile(r"(?<!\d)[2-9]\d{3}\s?\d{4}\s?\d{4}(?!\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_SENSITIVE_EXACT = frozenset(
    {
        "name",
        "full_name",
        "farmer_name",
        "contact_name",
        "village_name",
        "transcript",
        "message_text",
        "text",
        "body",
        "content",
    }
)
_SENSITIVE_SUBSTRINGS = ("phone", "mobile", "aadhaar", "aadhar", "address", "email", "password")


def _is_sensitive_key(key: str) -> bool:
    k = key.lower()
    return k in _SENSITIVE_EXACT or any(s in k for s in _SENSITIVE_SUBSTRINGS)


def redact_text(text: str) -> str:
    text = _PHONE_RE.sub(REDACTED, text)
    text = _AADHAAR_RE.sub(REDACTED, text)
    return _EMAIL_RE.sub(REDACTED, text)


def redact(obj: Any, *, _depth: int = 0) -> Any:
    """Return a copy of ``obj`` with sensitive keys blanked and PII patterns scrubbed from strings."""
    if _depth > 10:
        return REDACTED
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, Mapping):
        return {
            k: (REDACTED if isinstance(k, str) and _is_sensitive_key(k) else redact(v, _depth=_depth + 1))
            for k, v in obj.items()
        }
    if isinstance(obj, list | tuple | set | frozenset):
        return [redact(v, _depth=_depth + 1) for v in obj]
    return obj


def mask_phone(phone: str) -> str:
    """'+919876543210' -> '+91*****43210' style mask for operator UIs."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 6:
        return REDACTED
    return f"{'+' if phone.strip().startswith('+') else ''}{'*' * (len(digits) - 5)}{digits[-5:]}"


class Pseudonymizer:
    """HMAC-SHA256 pseudonyms. Deterministic per (salt, namespace, value); not reversible without the salt."""

    def __init__(self, salt: str | bytes) -> None:
        self._key = salt.encode() if isinstance(salt, str) else salt
        if not self._key:
            raise ValueError("salt must not be empty")

    def pseudonymize(self, namespace: str, value: str) -> str:
        msg = f"{namespace}\x1f{value}".encode()
        return hmac.new(self._key, msg, hashlib.sha256).hexdigest()[:24]
