# SDK Deliverables (Nexus MVP)

## Scope
- **Purpose**: Provider‑agnostic, SDK‑only plumbing to define and run agents with structured outputs, optional streaming, and optional local deterministic tools.
- **Out of scope**: Steer business logic, OA orchestration, stage policies, K×D replication logic, rubric content.

## Objectives (MVP)
- **Models**: Target OpenAI Responses API (GPT‑5 mini preferred; fallback 4.1‑mini).
- **Reliability**: Deterministic mode, strict JSON schema validation, idempotency.
- **Observability**: Normalized usage, latency, request identifiers, event callbacks.

## Capability Matrix (MVP)
- **Structured output (JSON schema)**: yes
- **Streaming deltas**: yes
- **Tool calling (local deterministic only)**: optional
- **Deterministic seed**: best‑effort; expose when provider supports
- **Timeouts/budgets**: request‑level ms/token limits
- **Retry & backoff**: typed transient retries with idempotency keys

## Core Interfaces (conceptual)
- **AgentDefinition**
  - system: str
  - user_template: str
  - json_schema: dict | None
  - model: str
  - parameters: { temperature?, top_p?, seed?, max_output_tokens?, extra? }
  - tools: list[Tool] | None

- **AgentRunner**
  - run(definition, variables, options) → AgentResult
  - options: { streaming: bool, deterministic: bool, budget: { tokens?, ms? }, metadata: dict }
  - events (callbacks or async iterator when streaming): on_delta, on_usage, on_completed

- **ProviderClient**
  - send(request) → provider_response
  - maps AgentDefinition → provider‑specific payload (Responses API, etc.)

- **Tool** (local deterministic)
  - name: str, description: str, json_schema: dict, handler: Callable
  - Called only if enabled by AgentDefinition and tool_choice policy allows

- **Validators**
  - validate_json_schema(data, schema) → data | raises
  - validate_annotation_schema(verdict) → verdict | raises

- **StreamAdapter** (optional)
  - normalize provider deltas → { type, text/json_delta, usage_partial }

## Responses API Mapping (OpenAI)
- Request fields to support:
  - model, input/messages, response_format (json schema), tools/tool_choice (when enabled)
  - parameters: temperature, top_p, max_output_tokens, seed (if available)
  - metadata: idempotency key, request labels (trace_id, run_id)
- Response handling:
  - parse structured output; enforce schema; capture usage (input/output tokens), latency, model version, request id
  - stream support: yield deltas and final structured result

## Determinism & Budgets
- deterministic: pass seed/analog where supported; otherwise clamp variability via parameters
- budgets: enforce max tokens and max wall‑clock with early abort (return partial with confidence if applicable)
- idempotency: require caller‑supplied idempotency_key; dedupe retried sends

## Error Handling
- Typed errors: ProviderError (client/server), TimeoutError, SchemaError, ToolError, RetryableError
- Retries: exponential backoff for retryable classes; never retry on SchemaError
- Rich context: include provider request_id, model, status_code, and hint

## Metrics & Logging
- Emit: request_id, model, latency_ms, input_tokens, output_tokens, cached?, retries, error_class
- Hooks: pluggable metrics sink; structured logs; sampling controls

## Configuration Flags (MVP)
- streaming: on/off
- deterministic: on/off (default on for CI)
- strict_json_schema: on (reject if invalid)
- enable_tools: off by default for MVP stages
- timeouts: connect_ms, total_ms

## Test Plan
- Unit: schema validation, tool adapter, deterministic parameter mapping
- Integration: golden fixtures for structured outputs; live sandbox run with seed → stable outputs within tolerance
- Error paths: simulated provider errors, retries, timeouts
- Conformance: capability registry correctly marks supported features per model

## Rollout
- Phase 1: Core AgentRunner + Responses client + JSON schema + metrics
- Phase 2: Streaming adapter + deterministic seed + idempotency
- Phase 3: Local tool support (schema_repair, annotation_dedup) gated by flag
- Phase 4: Additional providers (Anthropic, etc.) behind capability registry

## References
- See `docs/nexus/agent-sdk-guide.md` for scaffolding and usage patterns.
- See `docs/nexus/orchestrator-spec.md` for OA integration expectations.


