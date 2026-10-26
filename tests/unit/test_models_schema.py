"""Static checks on the ORM metadata: the PII boundary and required tables. No database needed."""

import pytest

from stubbleos.data.models import CORE, CORE_TABLES_REQUIRED, IMPACT_LABEL, PII, Base

FORBIDDEN_IN_CORE = ("full_name", "phone", "email", "address", "aadhaar", "village_name", "content")


def tables(schema: str) -> dict[str, object]:
    return {t.name: t for t in Base.metadata.tables.values() if t.schema == schema}


def test_every_table_is_in_core_or_pii() -> None:
    assert {t.schema for t in Base.metadata.tables.values()} == {CORE, PII}


def test_required_tables_exist() -> None:
    assert set(tables(CORE)) >= CORE_TABLES_REQUIRED


def test_pii_tables_are_exactly_the_identity_tables() -> None:
    assert set(tables(PII)) == {
        "farmer_identities",
        "operator_identities",
        "buyer_contacts",
        "conversation_messages",
    }


@pytest.mark.parametrize("name", sorted(CORE_TABLES_REQUIRED))
def test_no_pii_columns_in_core(name: str) -> None:
    table = Base.metadata.tables[f"{CORE}.{name}"]
    bad = [c.name for c in table.columns if any(f in c.name.lower() for f in FORBIDDEN_IN_CORE)]
    assert bad == []


def test_impact_records_cannot_be_unlabeled() -> None:
    table = Base.metadata.tables[f"{CORE}.impact_records"]
    names = {c.name for c in table.constraints if c.name}
    assert any("label_disclaimer" in n for n in names)
    assert "not registry-verified" in IMPACT_LABEL


def test_synthetic_flag_on_evidence_and_impact() -> None:
    for name in ("mrv_evidence", "impact_records"):
        assert "is_synthetic" in Base.metadata.tables[f"{CORE}.{name}"].columns
