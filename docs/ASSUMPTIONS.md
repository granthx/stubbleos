# Assumptions

Living list. Each item says what is assumed, why, and what would change it.

## Phase 1
1. **LLM provider default is `auto`**: Groq when `GROQ_API_KEY` is present, else Anthropic when `ANTHROPIC_API_KEY` is present, otherwise the deterministic `FakeLLM` (with a logged warning). Prevents CI and simulation runs from silently spending money. Simulation runs should set `STUBBLEOS_LLM_PROVIDER=fake` explicitly. The default model string is configurable via `STUBBLEOS_LLM_MODEL` (defaults to `llama-3.3-70b-versatile`).
2. **pgvector is deferred to Phase 6**, when the first vector-backed table (conversation memory, policy documents) is introduced. Until then the stock `postgis/postgis` image is used.
3. **Baseline migration uses `metadata.create_all`** (ADR-0004). All later migrations are explicit.
4. **Phone numbers are stored as plain text in the `pii` schema.** Application-level or column-level encryption is a Phase-7 hardening item, noted in `SAFETY_AND_ETHICS.md` when written.
5. **India has no DST**, so IST is a fixed +05:30 offset (`core.clock.IST`).
6. **Field polygons are not treated as PII** in `core`, but they can identify a household in a small village. Any export for external analysis must aggregate to village or district level. This is a policy rule to enforce in Phase 8, not something the schema prevents.
7. **Event delivery over Redis is at-most-once.** Durability and replay come from persisting events to `agent_events`.
8. **Landholding classes** follow the Indian agricultural-census size bands (marginal <1 ha, small 1-2, semi-medium 2-4, medium 4-10, large >10).
9. **Impact records are indicative.** The schema enforces the "not registry-verified" label with a CHECK constraint, and evidence/impact rows carry an `is_synthetic` flag that defaults to true.

## Verification status of Phase 1
See README "Verification status". In the authoring sandbox no third-party packages could be installed, so the test suite was written but not executed there.
