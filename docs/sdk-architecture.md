## SDK Architecture (Nexus-aligned, provider-agnostic)

### Purpose and scope
- Provide a clean, provider-agnostic SDK that exposes:
  - Direct LLM calls (generate, stream)
  - Agent primitives (definition → runner) with structured outputs
  - Optional local deterministic tools
  - Deterministic execution and idempotency helpers
  - Normalized streaming callbacks and metrics hooks
- Exclude: Orchestrator (OA) logic, A2A protocol, Steer business logic, domain event names.

### High-level modules
```
steer_llm_sdk/
├── llm/                 # provider integration
│   ├── providers/       # openai, anthropic, xai
│   ├── capabilities.py  # capability registry (per model)
│   └── router.py        # unified generate/stream entry points (BC)
├── agents/              # agent framework
│   ├── models/          # AgentDefinition, Options, Result
│   ├── runner/          # AgentRunner, StreamAdapter, EventManager
│   ├── validators/      # JSON schema + result validation
│   └── tools/           # Tool model + registry + executor (local deterministic)
└── models/              # shared request/response models
```

### Execution modes
1) Direct LLM calls (existing API, backward compatible)
   - Non-streaming: `SteerLLMClient.generate(messages, llm_model_id, params)`
   - Streaming: `SteerLLMClient.stream(...)/stream_with_usage(...)`
   - Use cases: ad hoc text generation, low-level primitives, legacy flow.

2) Agent runs (opt-in)
   - Define `AgentDefinition(system, user_template, model, parameters, json_schema?, tools?)`
   - Execute via `AgentRunner.run(definition, variables, options)`
   - Structured outputs enforced by JSON schema (native or post-hoc)
   - Optional streaming via callbacks (`on_start`, `on_delta`, `on_usage`, `on_complete`, `on_error`)

### Provider abstraction and capabilities
- Capability registry exposes per-model features:
  - `supports_json_schema`, `supports_streaming`, `supports_seed`, `supports_tools`, `uses_max_completion_tokens`, `max_context_length`, `max_output_tokens`.
- The runner/provider adapters consult capabilities to choose optimal paths.
- Models of interest:
  - `gpt-4.1-mini` (OpenAI) → Responses API supported
  - `gpt-5-mini` (OpenAI) → Responses API preferred
  - Anthropic (Claude) → Messages API; post-hoc schema validation
  - xAI (Grok) → Chat SDK; estimated usage when detailed usage unavailable

### Request mapping by provider
- OpenAI
  - Chat Completions (legacy): `model`, `messages`, `temperature`, `top_p`, `max_tokens|max_completion_tokens`, `stop`, `seed?`, `response_format?`
  - Responses API (preferred for `gpt-4.1-mini`, `gpt-5-mini`): `model`, `input` (role/content), `text.format={type:"json_schema", name, schema}`, `top_p`, `max_output_tokens`, `seed`, `stop?` (omit `temperature` for `gpt-5-mini`)
  - Streaming: SSE supported; normalized by the SDK; usage may emit at completion depending on provider behavior
  - See `docs/openai-responses-api.md` for details.

### Capability registry (decisions)
- Per-model flags drive request mapping and parameter support:
  - `supports_json_schema`, `supports_streaming`, `supports_seed`, `supports_temperature`, `uses_max_completion_tokens`.
- Providers avoid model-name heuristics; they consult capabilities.

### Determinism & retries
- Single clamp policy for deterministic runs; providers shouldn’t clamp ad-hoc.
- Typed errors and `RetryManager` handle transient failures without leaking provider specifics.
- Metrics: optional `MetricsSink` hook emits normalized usage and latency; keep sink pluggable (OTel optional).

- Anthropic (Claude)
  - Messages API: `system`, `messages`, `max_tokens`, `temperature`, `top_p`, `stop_sequences?`
  - No native JSON schema → parse text → JSON → validate; enable system prompt caching where supported.
  - Streaming events mapped into normalized deltas.

- xAI (Grok)
  - xai_sdk chat: `system/user/assistant` messages, sampling, streaming.
  - Usage may be estimated; cache_info empty.

### Structured outputs
- Native schema mode (OpenAI Responses API): send `response_format.json_schema` and return validated JSON.
- Post-hoc validation (providers without native schema): parse text → JSON → strict validation; on failure raise `SchemaError`. Optional local tools:
  - `json_repair`: attempt to fix formatting
  - `format_validator`: shape checks
  - `extract_json`: extract JSON from mixed text

### Streaming model
- Normalized callbacks across providers:
  - `on_start(meta)`
  - `on_delta({ type: "text"|"json", value })`
  - `on_usage(usage)` (in-stream if supported, else at completion)
  - `on_complete(result)`
  - `on_error(error)`
- `StreamAdapter` converts provider-specific deltas to the normalized shape.

### Determinism & idempotency
- Deterministic mode:
  - Clamp parameters (e.g., `temperature=0`, `top_p<=0.1`) via a centralized policy.
  - Propagate `seed` only when `supports_seed=True`.
- Idempotency:
  - Optional `idempotency_key` in options; in-memory `IdempotencyManager` provides dedup (TTL + LRU) for retries.

### Tools (local deterministic)
- Tools defined by name, description, JSON schema for parameters, and a deterministic handler.
- SDK validates parameters and executes tool handlers locally; results can be fed into the next LLM turn.
- Off by default; enabled per agent.

### Errors & retries
- Typed errors: `AgentError`, `ProviderError`, `SchemaError`, `ToolError`, `TimeoutError`, `BudgetExceededError`.
- `RetryManager` with explicit retryable error classes and exponential backoff; integrates with idempotency.

### Metrics & logging
- Normalized usage: `prompt_tokens`, `completion_tokens`, `total_tokens`, `cache_info?`.
- Cost calculation driven by per-model pricing in `config/models.py`.
- Metrics hooks via `MetricsSink` protocol; optional OpenTelemetry sink.
- Providers use structured logging (no prints in library code paths).

### Configuration & environment
- API keys via environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY`).
- Timeouts and feature flags via env or options.
- Capability registry and model configs sourced from `config/models.py`.

### Backward compatibility
- Existing `SteerLLMClient` generate/stream APIs remain unchanged.
- Agents are opt-in; no OA/stage semantics in the SDK.

### How each type is handled
- Direct calls (Chat Completions): lowest common denominator; no schema guarantees; streaming supported.
- Direct calls (Responses API): preferred for models that support it; native schema + better metadata/streaming; used when a schema is provided.
- Agents: wrap either path based on capabilities; enforce schema; optional tools; deterministic/idempotent; normalized streaming.

### References
- OpenAI Responses API: `docs/openai-responses-api.md`
- SDK deliverables and agent guide: `docs/nexus/sdk-deliverables.md`, `docs/nexus/agent-sdk-guide.md`



### MVP Implementation Plan (clear separation, minimal changes)

Guiding constraints:
- Preserve existing direct calls and streaming; no breaking API changes.
- Clean separation: providers (I/O only), router (wires), agents (composition/validation), utilities (capabilities, determinism, metrics).
- Keep files small: target ≤ 200 LOC; hard max ≤ 400 LOC per file.
- Avoid over-engineering: deliver Responses API, Agents MVP, and minimal refactors only.

Workstreams and deliverables:

- Workstream A: Capabilities + Determinism (Day 1)
  - `llm/capabilities.py` (≤ 120 LOC): central model capability flags per model (done; extend as needed).
  - `agents/runner/determinism.py` (≤ 120 LOC): `apply_deterministic_policy(params, caps)`; clamp temperature/top_p, propagate seed if supported.
  - Acceptance: unit tests for policy mapping on `gpt-4.1-mini`, `gpt-5-mini`, `o4-mini`.

- Workstream B: OpenAI Responses API (Day 2–3)
  - Update `llm/providers/openai.py` (keep < 400 LOC total) to:
    - Route to Responses API for `gpt-4.1-mini` and `gpt-5-mini` when `response_format.json_schema` provided.
    - Map `max_output_tokens` vs `max_tokens` via capabilities.
    - Keep Chat Completions path as fallback; preserve streaming behavior.
  - Add streaming via Responses API (SSE) if available; otherwise keep existing streaming.
  - Acceptance:
    - Non-streamed structured output returns validated JSON string/body.
    - Streaming yields deltas and final usage (either in-stream or at completion).
    - Golden tests for both models with schema.

- Workstream C: Agents MVP (Day 3–5)
  - `agents/models/{agent_definition.py, agent_options.py, agent_result.py}` (each ≤ 150 LOC).
  - `agents/validators/json_schema.py` (≤ 150 LOC): strict validation helper. Add `jsonschema` dependency.
  - `agents/runner/{agent_runner.py, event_manager.py, stream_adapter.py}` (each ≤ 200 LOC):
    - Runner composes system + user_template (Jinja2 already in deps), applies determinism, picks provider path via capabilities, enforces schema (native or post-hoc), maps streaming callbacks (`on_start/on_delta/on_usage/on_complete/on_error`).
  - Optional minimal tool: `extract_json` only (skip others until later).
  - Acceptance: basic agent example runs against 4.1-mini and 5-mini; schema enforced; streaming callbacks invoked.

- Workstream D: Cleanup + Separation (Day 5)
  - Remove prints from providers; use logger.
  - Normalize usage dict shape across providers.
  - Keep `llm/router.py` framework-agnostic (no FastAPI imports in core logic).
  - Enforce file size budget (script in tests to assert LOC < 400 for SDK python files).

- Workstream E: Tests & Docs (Day 5–6)
  - Unit: capabilities, determinism, schema validator, stream adapter.
  - Integration: OpenAI Responses API for `gpt-4.1-mini` and `gpt-5-mini` (mock or live gated by env).
  - Update docs: link `docs/openai-responses-api.md`; refresh `IMPLEMENTATION_PLAN.md` with current status.

Sequenced PRs (small and reviewable):
- PR1: Capabilities + Determinism helper + tests.
- PR2: OpenAI Responses API path (non-stream) + tests.
- PR3: Responses streaming (if available) + unified usage mapping.
- PR4: Agents MVP (models, runner, validator, minimal tool) + examples + tests.
- PR5: Cleanup (logging, usage normalization, LOC guard) + docs refresh.

Acceptance criteria (MVP):
- Backward-compatible: existing generate/stream code paths unchanged; tests green.
- Responses API functional for `gpt-4.1-mini` and `gpt-5-mini` with schema, including streaming.
- Agents MVP runs with deterministic option and schema validation across supported providers.
- No file exceeds 400 LOC; most new files ≤ 200 LOC; lint passes.

Notes on non-goals (defer):
- Full tool-calling loop beyond `extract_json`.
- Rich retry/backoff and metrics sinks (wire hooks only; keep defaults minimal).
- OA/A2A protocol specifics or domain event naming.
