import pytest

from stubbleos.core.privacy import REDACTED, Pseudonymizer, mask_phone, redact, redact_text


@pytest.mark.parametrize(
    "raw",
    ["9876543210", "+91 9876543210", "+919876543210", "91-9876543210", "0091 9876543210"],
)
def test_phone_numbers_redacted(raw: str) -> None:
    assert redact_text(f"call {raw} now") == f"call {REDACTED} now"


def test_aadhaar_and_email_redacted() -> None:
    out = redact_text("id 2345 6789 0123 mail a.b@example.com")
    assert "2345" not in out
    assert "example.com" not in out


def test_non_pii_numbers_survive() -> None:
    assert (
        redact_text("field 12 has 4.5 acres, deadline in 14 days")
        == "field 12 has 4.5 acres, deadline in 14 days"
    )


def test_sensitive_keys_blanked_recursively() -> None:
    out = redact({"farmer_name": "X", "nested": [{"phone_e164": "1", "ok": 5}], "district": "Ludhiana"})
    assert out["farmer_name"] == REDACTED
    assert out["nested"][0]["phone_e164"] == REDACTED
    assert out["nested"][0]["ok"] == 5
    assert out["district"] == "Ludhiana"


def test_mask_phone() -> None:
    assert mask_phone("+919876543210").endswith("43210")
    assert "98765" not in mask_phone("+919876543210")
    assert mask_phone("12") == REDACTED


def test_pseudonymizer_properties() -> None:
    a, b = Pseudonymizer("salt-a"), Pseudonymizer("salt-b")
    assert a.pseudonymize("farmer", "42") == a.pseudonymize("farmer", "42")
    assert a.pseudonymize("farmer", "42") != a.pseudonymize("operator", "42")
    assert a.pseudonymize("farmer", "42") != b.pseudonymize("farmer", "42")
    with pytest.raises(ValueError, match="salt"):
        Pseudonymizer("")
