# ADR-0003: PII separation by schema, pseudonyms and redacting logs

**Status:** accepted

**Decision.** Two Postgres schemas: `core` (analytics-safe) and `pii` (names, phones, buyer contacts, raw message text). `core.farmers` carries an HMAC pseudonym, never a name or phone. Logging always runs a redaction processor (`core.privacy.redact`). A unit test asserts that no `core` column name looks like PII.

**Why.** Separation lets analytics, simulation exports and dashboards work without PII access, and makes erasure a targeted operation (null `pii` columns, set `erased_at`).

**Limits.** Redaction is pattern-based and a safety net only. Field geometry can still identify a household (ASSUMPTIONS #6). Encryption at rest for `pii` columns is deferred.
