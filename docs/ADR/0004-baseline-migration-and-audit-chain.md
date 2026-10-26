# ADR-0004: Baseline migration via `create_all`; hash-chained append-only audit log

**Status:** accepted, with a stated shortcut

**Decision (migration).** Revision 0001 calls `Base.metadata.create_all`. This is acceptable only because no database predates it. From revision 0002 onward migrations must be explicit.

**Why.** Hand-writing about 25 `create_table` calls in a sandbox that cannot run Alembic invites silent divergence from the models.

**Risk.** The baseline is not frozen against future model edits. Mitigation: once 0002 exists, 0001 should be regenerated as explicit operations from a database built by 0001. Tracked in ROADMAP.

**Decision (audit).** `core.audit_log` entries carry `prev_hash` and `entry_hash` (SHA-256 over canonical JSON). A Postgres trigger blocks UPDATE, DELETE and TRUNCATE. The application verifies the chain with `AuditLogRepository.verify_chain`.

**Limits.** The chain detects tampering by anyone who edits rows without recomputing the chain; a database superuser can bypass triggers. Anchoring the head hash externally would close that gap and is out of scope for the MVP.
