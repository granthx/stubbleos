"""Needs a live PostGIS database at STUBBLEOS_DATABASE_URL. Run: make up && make test-int"""

import os
import subprocess
import sys
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, OperationalError

from stubbleos.core.config import Settings
from stubbleos.data.models import CORE, CORE_TABLES_REQUIRED, PII

pytestmark = pytest.mark.integration


def alembic(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "alembic", *args], check=True, env=os.environ.copy())  # noqa: S603


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    url = Settings(_env_file=None).database_url  # type: ignore[call-arg]
    eng = create_engine(url)
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("no Postgres reachable at STUBBLEOS_DATABASE_URL")
    yield eng
    eng.dispose()


def test_upgrade_creates_schema_and_audit_log_is_immutable(engine: Engine) -> None:
    alembic("downgrade", "base")
    alembic("upgrade", "head")
    with engine.begin() as c:
        core = {
            r[0]
            for r in c.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"), {"s": CORE}
            )
        }
        pii = {
            r[0]
            for r in c.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"), {"s": PII}
            )
        }
        assert core >= CORE_TABLES_REQUIRED
        assert pii == {"farmer_identities", "operator_identities", "buyer_contacts", "conversation_messages"}
        c.execute(
            text(
                "INSERT INTO core.audit_log (ts, actor, action, entity_type, details, prev_hash, entry_hash) "
                "VALUES (now(), 'a', 'x', 't', '{}', :p, :h)"
            ),
            {"p": "0" * 64, "h": "1" * 64},
        )
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
        c.execute(text("UPDATE core.audit_log SET actor = 'mallory'"))
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
        c.execute(text("DELETE FROM core.audit_log"))
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
        c.execute(text("TRUNCATE core.audit_log"))


def test_impact_label_constraint_rejects_unlabeled_rows(engine: Engine) -> None:
    alembic("upgrade", "head")
    with pytest.raises(DBAPIError, match="label_disclaimer"), engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO core.impact_records (id, field_id, season, status, label, burn_avoided, area_acres, "
                "method_note, evidence_ids, record_sha256) VALUES (gen_random_uuid(), gen_random_uuid(), 's', "
                "'indicative', 'verified carbon credit', true, 1, '', '[]', 'x')"
            )
        )


def test_downgrade_is_clean(engine: Engine) -> None:
    alembic("downgrade", "base")
    with engine.begin() as c:
        left = c.execute(
            text("SELECT count(*) FROM information_schema.schemata WHERE schema_name IN ('core','pii')")
        ).scalar_one()
    assert left == 0
    alembic("upgrade", "head")
