## Nexus SDK MVP – Implementation Report

### Executive summary
- Provider‑agnostic SDK upgraded for Nexus with agent primitives, OpenAI Responses API integration (GPT‑4.1 mini, GPT‑5 mini), deterministic mode, idempotency, local tools, typed errors/retries, metrics hooks, normalized streaming, and smoke tests/CI.
- Backward compatibility preserved for existing `SteerLLMClient` generate/stream.

### Goals
- **Separation of concerns**: SDK handles providers, structured outputs, streaming, and deterministic execution; OA/orchestrator logic remains outside.
- **Provider‑agnostic**: capability registry drives behavior; no model‑name heuristics.
- **Deterministic & reliable**: seeded runs (where supported), parameter clamps, idempotency, retries, typed errors.
- **Observability**: normalized usage, cost and optional metrics sink.

### What shipped
- Agents: `AgentDefinition`, `AgentOptions`, `AgentResult`; `AgentRunner` with evented streaming and schema validation.
- Providers: OpenAI adapter with Responses API (`text.format=json_schema`, schema root `additionalProperties=false`, omits `temperature` for GPT‑5 mini); Anthropic and xAI adapters cleaned up and normalized.
- Capabilities: per‑model flags (`supports_json_schema`, `supports_streaming`, `supports_seed`, `supports_temperature`, `uses_max_completion_tokens`, `fixed_temperature`).
- Determinism & idempotency: central clamp helper; in‑memory `IdempotencyManager` (TTL + LRU).
- Tools: local deterministic tools scaffold; built‑ins `extract_json`, `format_validator`, `json_repair`; schema‑from‑callable helper.
- Streaming: normalized callbacks (`on_start`, `on_delta`, `on_usage`, `on_complete`, `on_error`); JSON delta support; usage emitted once on completion when not in-stream.
- Errors & retries: typed `ProviderError`; runner wraps provider calls and retries transient errors.
- Metrics: `AgentMetrics` and pluggable `MetricsSink`; optional OTel sink.
- Tests & CI: smokes for Responses API, strict/instructions, determinism, retry, and back‑compat; ruff lint + 400 LOC per file guard.

### Key decisions
- Prefer OpenAI Responses API over Chat Completions for structured output; enforce JSON schema root invariants.
- Use capability registry to avoid hard‑coded model branches.
- Keep tools local/deterministic; no external calls in tools for MVP.

### Architecture overview (high‑level)
- See `docs/sdk-architecture.md` for modules and flows.
- See `docs/reports/NEXUS_SDK_ARCHITECTURE.md` for ASCII diagrams.

### Provider integration details
- OpenAI (Responses API)
  - Structured output via `text.format={ type: "json_schema", name, schema, strict? }`.
  - GPT‑5 mini: omit `temperature`; rely on `top_p`/schema.
  - Capability‑driven selection of `max_output_tokens` vs `max_tokens`.
  - Optional pass‑through: `responses_use_instructions`, `reasoning`, `metadata`.
- Anthropic/xAI
  - No native JSON schema; post‑hoc validation performed by runner.
  - Usage dict normalized (prompt/completion/total tokens + cache_info).

### Determinism & idempotency
- Clamp policy (deterministic=True): set temperature to 0.0 (unless fixed/unsupported), limit top_p, propagate seed only if supported.
- In‑memory idempotency with TTL (15m) and LRU (~1000 entries) for retry dedupe.

### Tools
- `extract_json(text)` – finds first JSON object/array and parses.
- `format_validator(output, schema)` – validates output against schema.
- `json_repair(text, schema?)` – deterministic heuristics to fix minor JSON issues, then validate.
- `schema_from_callable(func)` – best‑effort JSON schema for function parameters.

### Streaming
- Evented callbacks and JSON delta support; usage emitted once when in‑stream usage isn’t provided by the provider.
- Map Responses API SSE events to normalized deltas.

### Errors & retries
- Typed `ProviderError`; runner retries once (configurable) for transient provider failures.

### Metrics
- `AgentMetrics` emitted (request_id, trace_id, model, latency_ms, tokens, cached_tokens, retries, error_class, tools_used).
- Optional OTel sink (`agents/metrics_sink_otlp.py`); no dependency if absent.

### Backward compatibility
- `SteerLLMClient.generate/stream` work unchanged; smoke tests added.

### Tests & CI
- Smokes: Responses API (gpt‑4.1‑mini, gpt‑5‑mini), strict/instructions mapping, determinism (two runs equal), retry path, back‑compat client.
- CI: ruff lint and 400 LOC guard on SDK files.

### Migration notes (from pre‑Nexus)
- To get structured outputs on OpenAI:
  - Provide `json_schema` in `AgentDefinition` (runner will pick Responses API for supported models).
  - Optionally set `strict=True` and `responses_use_instructions=True` in `AgentOptions.metadata`.
- Tools are local and off by default; attach as needed.
- Deterministic mode is opt‑in via `AgentOptions`.

### Next steps (post‑MVP)
- More built‑in tools (annotation dedup, span checks).
- Optional richer metrics sink docs & samples.
- Additional provider models behind capability registry.


