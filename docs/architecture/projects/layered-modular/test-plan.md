## Test Plan – Layered Modular SDK

### Scope
Validate routing decisions, capability-driven behavior, normalization, streaming, errors/retries, and backward compatibility.

### Test suites
- Smoke (online)
  - OpenAI Responses API: GPT‑4.1 mini & GPT‑5 mini structured outputs with `strict=True`, streaming and non‑stream.
  - Determinism: two seeded runs → identical content.
  - Retry path: transient `ProviderError` retried successfully.
  - Back‑compat: `SteerLLMClient.generate/stream` happy paths.
- Unit (offline)
  - Capability registry lookups and param mapping (max_tokens vs max_output_tokens, temperature omission for GPT‑5 mini).
  - Usage normalization across providers; missing fields defaulting.
  - StreamAdapter: text/JSON delta normalization.
  - Determinism clamp policy.
  - Idempotency TTL/LRU behavior.

### Invariants
- Usage dict always contains prompt/completion/total tokens; `cache_info` dict present (possibly empty).
- `on_usage` emitted exactly once when not available in‑stream.
- Provider adapters raise typed `ProviderError` on transport failures.

### Tooling
- `pytest -q` for unit/smoke; optional markers for online tests.
- Future: add mypy checks for adapter contracts.


