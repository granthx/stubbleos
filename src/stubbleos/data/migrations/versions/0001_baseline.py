"""Baseline schema: core + pii schemas, all tables, audit-log immutability trigger.

DELIBERATE SHORTCUT (ADR-0004): this baseline calls ``metadata.create_all`` instead of listing every
table. That is acceptable ONLY because no database exists before this revision. Every later migration
MUST be explicit (op.add_column, op.create_table, ...), never ``create_all``.

Revision ID: 0001
Revises:
"""

from alembic import op

from stubbleos.data.models import CORE, PII, Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_IMMUTABLE_FN = f"""
CREATE OR REPLACE FUNCTION {CORE}.audit_log_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {CORE}")
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {PII}")
    Base.metadata.create_all(bind=op.get_bind())
    op.execute(_IMMUTABLE_FN)
    op.execute(
        f"CREATE TRIGGER audit_log_no_update_delete BEFORE UPDATE OR DELETE ON {CORE}.audit_log "
        f"FOR EACH ROW EXECUTE FUNCTION {CORE}.audit_log_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON {CORE}.audit_log "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {CORE}.audit_log_immutable()"
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS audit_log_no_truncate ON {CORE}.audit_log")
    op.execute(f"DROP TRIGGER IF EXISTS audit_log_no_update_delete ON {CORE}.audit_log")
    Base.metadata.drop_all(bind=op.get_bind())
    op.execute(f"DROP FUNCTION IF EXISTS {CORE}.audit_log_immutable()")
    op.execute(f"DROP SCHEMA IF EXISTS {PII} CASCADE")
    op.execute(f"DROP SCHEMA IF EXISTS {CORE} CASCADE")
