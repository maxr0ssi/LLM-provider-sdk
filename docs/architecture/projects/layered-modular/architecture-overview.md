## SDK Layered & Modular Architecture

### Purpose
Define clear layers and contracts so we can easily add providers, models, on‑prem/local runtimes, and provider‑native agent adapters without changing core behavior or breaking backward compatibility.

### High‑level stack
```text
+----------------------------+
| User App / Orchestrator    |
+----------------------------+
              |
              v
+-----------------------------------------------+
| Public API Layer                               |
| - SteerLLMClient (generate/stream/with_usage)  |
| - Agent primitives (Definition/Runner/Tools)   |
+-----------------------------------------------+
              |
              v
+-----------------------------------------------+
| Decision & Normalization Layer                 |
| - Decide: Call | Agent                         |
| - Param Normalizer (max_tokens vs max_output)  |
| - Message shaping (system/user/instructions)   |
| - Usage normalization                          |
+-----------------------------------------------+
              |
              v
+-----------------------------------------------+
| Capability & Policy Layer                      |
| - Capability Registry                          |
| - Determinism (clamps, seed)                   |
| - Budgets (tokens/time)                        |
+-----------------------------------------------+
              |
              v
+-----------------------------------------------+
| Routing Layer                                  |
| - LLMRouter (agnostic)                         |
| - Select Provider Adapter by model/provider    |
+-----------------------------------------------+
              |
              v
+-----------------------------------------------+
| Provider Adapter Layer                         |
| - OpenAI Adapter (Chat/Responses)              |
| - Anthropic Adapter                            |
| - xAI Adapter                                  |
| - Future: Local/On‑prem Adapter                |
+-----------------------------------------------+
              |
              v
+-----------------------------------------------+
| Streaming & Events Layer                       |
| - on_start/on_delta/on_usage/on_complete/...   |
| - StreamAdapter (normalize text/JSON deltas)   |
+-----------------------------------------------+
              |
              v
+-----------------------------------------------+
| Errors, Retries & Idempotency                  |
| - Typed errors, RetryManager, Idempotency      |
+-----------------------------------------------+
              |
              v
+-----------------------------------------------+
| Metrics & Observability                        |
| - AgentMetrics + MetricsSink (optional OTLP)   |
+-----------------------------------------------+
              |
              v
+-----------------------------------------------+
| Optional Provider‑Native Agent Adapters        |
| - OpenAI Agents SDK Adapter (outside core)     |
| - Future: Anthropic/XAI/Google adapters        |
+-----------------------------------------------+
```

### Layer goals and boundaries
- **Public API Layer (SDK surface)**: Stable user‑facing APIs. No provider‑specific code here. Backward compatibility guaranteed for existing methods.
- **Decision & Normalization**: Data‑shape consistency. All parameters validated and mapped before hitting providers.
- **Capability & Policy**: Behavior driven by capabilities, not if/else by model name. Determinism/budgets centralized.
- **Routing**: Single place that selects provider adapter. No business logic.
- **Provider Adapters**: Small, focused translators to provider SDKs/APIs. No cross‑provider logic here.
- **Streaming & Events**: Provider‑agnostic event bus; adapters emit normalized events.
- **Errors/Retries/Idempotency**: Reliability features isolated; providers raise typed errors, runner handles retries/idempotency.
- **Metrics**: Pluggable, optional; never blocks request paths.
- **Provider‑Native Agent Adapters**: Out of core. Keep vendor lock‑in here only.

### Core contracts (must remain stable)
- **Provider Adapter interface**
  - `async generate(messages, params) -> GenerationResponse`
  - `async generate_stream(messages, params) -> Async[str]`
  - `async generate_stream_with_usage(messages, params) -> Async[tuple[str|None, dict|None]]`
  - Emits normalized usage: `{prompt_tokens, completion_tokens, total_tokens, cache_info?}`

- **GenerationParams** (selected fields)
  - Common: `temperature?`, `top_p?`, `max_tokens? | max_output_tokens?`, `stop?`, `metadata?`
  - Determinism: `seed?`
  - Structured output: `response_format?` (JSON schema) when supported
  - Responses API flags: `responses_use_instructions?`, `strict?`, `reasoning?`

- **Agent primitives**
  - `AgentDefinition(system, user_template, json_schema?, model, parameters?, tools?)`
  - `AgentRunner.run(definition, variables, options)` returns `AgentResult(content, usage, model, elapsed_ms, provider_metadata, trace_id)`
  - Streaming via callbacks (on_start, on_delta, on_usage, on_complete, on_error)

### Extension playbooks
- **Add a new provider**
  - Implement the Provider Adapter interface described above.
  - Normalize usage and map param names (`max_tokens` vs `max_output_tokens`).
  - Update provider registry in `LLMRouter` and add capability entries for its models.
  - Add smoke tests: generate, stream, usage shape; if no native schema support, post‑validate JSON.

- **Add a new model**
  - Add to Capability Registry with accurate flags (schema/seed/streaming/temperature support, token field names, fixed temperature).
  - If OpenAI and JSON schema is required: ensure Responses API path uses `text.format` and root `additionalProperties=false`.
  - Add a smoke test for generate(+schema if supported) and stream.

- **Add a local/on‑prem runtime**
  - Create a Provider Adapter that talks to your local server/runtime API.
  - Normalize usage and deltas; add to router; add tests.

- **Add a provider‑native agent adapter (optional)**
  - Create in an `integrations/` module outside core.
  - Map `AgentDefinition` → provider agent constructs; bridge streaming events; handle strict schema and determinism.
  - Keep as an optional dependency; document install and usage.

### Parameter normalization rules (examples)
- `max_tokens` vs `max_output_tokens`: consult capability; map accordingly.
- `temperature`: omit when unsupported (e.g., GPT‑5 mini in Responses API) or clamp under determinism.
- `response_format` (JSON schema): only send for models that support schema natively; else post‑validate.
- `seed`: forward only when supported.

### Usage normalization rules
- Always return: `prompt_tokens`, `completion_tokens`, `total_tokens`.
- `cache_info`: dict when available; else `{}`.
- Emit usage at end of streaming when in‑stream usage isn’t available.

### Error & retry policy
- Provider raises `ProviderError` for transport/transient failures.
- Runner retries retryable errors with exponential backoff (configurable).
- Schema violations raise `SchemaError` in non‑stream path or on completion in streaming.

### Observability
- Emit `AgentMetrics` on completion (best‑effort). Do not let metrics failures impact result.
- Optional OTLP sink provided; not a hard dependency.

### Backward compatibility
- Preserve `SteerLLMClient` behavior and signatures.
- Changes to internal layers must not break public API; evolve via capabilities and normalization.

### CI & quality gates
- Lint via ruff; ≤400 LOC per file in SDK.
- Smoke tests for new providers/models; determinism and retry paths covered.

### Future‑proofing
- Keep capabilities authoritative for behavior changes.
- Encapsulate vendor‑specific features in adapters or integrations.
- Favor composition over flags in core APIs; keep public API minimal and stable.


