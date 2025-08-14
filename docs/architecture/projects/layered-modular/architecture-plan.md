## Architecture Plan – Layered Modular SDK

### Target structure (logical)
- Public API Layer
  - Steer client surface (generate, stream, stream_with_usage)
  - Agents API exports (AgentDefinition, AgentRunner, Tools)
- Decision & Normalization Layer
  - Parameter normalization (e.g., max_tokens vs max_output_tokens)
  - Message shaping (system/user; optional instructions mapping)
  - Usage normalization (prompt/completion/total/cache_info)
- Capability & Policy Layer
  - Model capability registry (schema/seed/streaming/temperature, token param name)
  - Determinism policy (clamps, seed propagation)
  - Budgets (tokens/time)
- Routing Layer
  - Provider‑agnostic router
  - Provider selection by model + capability flags
- Provider Adapter Layer
  - OpenAI adapter (Chat + Responses API)
  - Anthropic adapter
  - xAI adapter
  - Local/on‑prem adapter placeholder
- Streaming & Events Layer
  - Unified callbacks (on_start, on_delta, on_usage, on_complete, on_error)
  - Stream delta normalization (text/JSON)
- Reliability Layer
  - Typed errors, retry manager, idempotency manager
- Metrics & Observability Layer
  - Metrics model and optional sinks (e.g., OTLP)
- Agents (Primitives)
  - AgentDefinition/Options/Result models
  - AgentRunner orchestrating policies, streaming, retries
  - Tools (built‑ins, executor, schema‑from‑callable)

Notes:
- Physical file moves optional; we can alias current paths to avoid churn. The key is enforcing the contracts between layers.

### Stable interfaces
- Provider Adapter interface (unchanged) and streaming tuple protocol.
- GenerationParams schema: add `responses_use_instructions`, `strict`, `reasoning`, `metadata` fields formally.
- Usage dict shape: enforce `{prompt_tokens, completion_tokens, total_tokens, cache_info}`.

### Capability registry
- One source of truth for each model’s features: schema/seed/streaming support, token field names, fixed/unsupported temperature, max token param name.
- Drive router/request shaping via this registry only.

### Decision policy
- If `agent_mode=True` or `json_schema` present or `tools` attached → Agent path; else Call path.
- For OpenAI schema path, use Responses API with `text.format` and root `additionalProperties=false`; omit `temperature` for `gpt-5-mini`.

### Error and retry
- Providers raise `ProviderError`; Runner applies `RetryManager` for retryable failures; `SchemaError` for schema failures.

### Metrics
- Keep optional sink; emit once per run with normalized usage and latency.


