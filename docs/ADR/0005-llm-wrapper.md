# ADR-0005: Provider-agnostic LLM wrapper with `auto` selection

**Status:** accepted

**Decision.** `LLMClient` is a small protocol (`generate`, `generate_structured`). Implementations: `GroqLLM`, `AnthropicLLM` and a deterministic scriptable `FakeLLM`. `STUBBLEOS_LLM_PROVIDER=auto` picks Groq when `GROQ_API_KEY` exists, else Anthropic when `ANTHROPIC_API_KEY` exists, otherwise the fake with a warning. Structured output is prompt-based with Pydantic validation and an error-feedback retry; model output is never trusted unvalidated. Every client keeps a `UsageMeter` that feeds the coordination-overhead metric.

**Why.** Tests and simulations must run offline and reproducibly; production should default to the real provider. `FakeLLM` raises when nothing is scripted, so tests cannot pass on invented text.

**Consequences.** Prompts live in a versioned registry (`llm.prompts`), not inline strings.
