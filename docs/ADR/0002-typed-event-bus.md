# ADR-0002: Typed event envelope with registry; Redis pub/sub plus durable log

**Status:** accepted

**Decision.** Agents communicate through registered `EventPayload` models inside an `Event` envelope. Two buses: `InMemoryEventBus` (sequential, deterministic; used in tests and simulation) and `RedisEventBus` (cross-process pub/sub). Every event is also persisted to `agent_events` via `PersistingEventSink`.

**Why.** Typed messages make agent contracts testable and prevent free-text coupling. Sequential in-memory delivery keeps simulation runs reproducible. Redis pub/sub is simple but at-most-once, so durability and replay come from the database log instead of Redis.

**Alternatives.** Redis Streams (durable, consumer groups) are the likely upgrade if multi-process replay becomes a requirement. Not needed for the simulation-first MVP.

**Consequences.** New event types require a payload class and registration. Handlers must be idempotent (events can be redelivered after an outage).
