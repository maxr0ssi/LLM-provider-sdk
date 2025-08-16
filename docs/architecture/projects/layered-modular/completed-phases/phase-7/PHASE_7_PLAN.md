## Phase 7 – Agents Integrations as a Core Runtime (Plan)

### Objective
- Elevate “integrations” from optional add‑ons to a first‑class, core runtime for vendor‑native Agent SDKs, starting with the OpenAI Agents SDK.
- Provide a unified, provider‑agnostic Agents Runtime interface so future agent SDKs (e.g., Anthropic) can plug in without changing public APIs.
- Preserve our existing contracts: normalized streaming events, usage, determinism, error taxonomy, and observability.

### Outcomes
- Users can select `runtime="openai_agents"` in `AgentRunner` and get the same normalized behavior (results, events, usage, errors, metrics) as the router/provider path.
- OpenAI Agents SDK becomes a supported execution path in core, behind a clean interface and a lazy/optional dependency gate.
- Docs, tests, and diagrams for the runtime layer are complete and discoverable.

### Scope
- In scope: Core runtime layer, OpenAI adapter, normalization, observability hooks, testing, and docs.
- Out of scope (Phase 7): Additional providers’ agent SDKs (placeholders and interface parity only), voice/Realtime, hosted tools, and multi‑agent handoffs (kept compatible but not a focus).

### Non‑Goals
- Changing our public API signatures.
- Embedding vendor‑specific semantics into non‑integration layers (capabilities/normalization/routing remain provider‑agnostic).

### Architecture (high level)
- New core layer: `steer_llm_sdk/integrations/agents/`
  - `base.py` – `AgentRuntimeAdapter` ABC + normalized models
  - `openai/adapter.py` – OpenAI Agents SDK implementation
  - `mapping.py` – schema/params/tools/error mapping helpers
  - `streaming.py` – event bridge to `EventManager`/`StreamAdapter`
  - `errors.py` – integration error normalization → `ProviderError`/`SchemaError`
  - `__init__.py` – exports and factory (`get_agent_runtime("openai_agents")`)
- Runner integration: `AgentRunner` accepts `runtime` and delegates to an `AgentRuntimeAdapter` when set.
- Capability registry reused to drive schema/seed/temperature/tokens decisions inside runtime.

### External Monitoring & API
- Metrics: extend `MetricsCollector` with `agent_runtime` dimension, `ttft_ms`, `chunks`, `tools_invoked`, `agent_loop_iters`, `handoffs`, `retry_count`, error category.
- Suggested host app endpoints:
  - `/health/agents` – runtime presence + dependency/creds checks per provider.
  - `/metrics` – expose OTLP/Prom; SDK emits to sinks.
  - `/agents/runs/{id}` – optional run snapshots (request_id, provider/model, ttft, usage, errors). SDK provides a serializable snapshot object.
- Tracing: accept `trace_id` in options; propagate vendor trace IDs into `provider_metadata`; correlate with external tracing.

### How OpenAI Agents work (mapping context)
- Agent loop: invoke LLM ↔ tools until final output; adapter preserves loop semantics but emits normalized events.
- Tools: `@function_tool` from typed Python functions; adapter mirrors our deterministic local tools into Agents SDK tool specs.
- Structured outputs: Responses `text.format` with root `additionalProperties=false`; strict when supported; always post‑validate.

### Deliverables
- Core runtime interface and models.
- OpenAI Agents SDK adapter with streaming, usage, determinism, errors, and metrics wired.
- Docs: Plan, Technical Design, Integration Guide, and diagrams.
- Tests: unit, conformance, and optional online smokes.

### Timeline (2–3 weeks)
- Week 1
  - Create runtime layer (`base.py`, `models`, helpers) and OpenAI adapter (non‑stream happy path + schema).
  - Wire `AgentRunner.runtime` with factory resolution.
  - Unit tests: definition→agent mapping, schema/params mapping.
- Week 2
  - Streaming bridge + usage aggregation + JSON handler integration.
  - Determinism/budgets + error mapping + metrics.
  - Conformance tests + docs + examples; optional online smokes.
- Week 3
  - Perf polish (<1ms/event), edge‑case coverage (tools, large JSON), health/metrics guidance; Anthropic adapter stubs.

### Risks & Mitigations
- API drift in vendor SDK → keep adapter thin; pin supported versions; defensive unit tests.
- Schema edge cases → strict mode where supported; universal post‑validation; clear `SchemaError` paths.
- Streaming variance → normalized events + JSON dedup; finalize usage at end when absent in‑stream.
- Perf overhead → lazy import; opt‑in JSON handler; event pipeline under 1ms.

### Acceptance Criteria
- `AgentRunner(runtime="openai_agents")` returns normalized `AgentResult` and emits typed events identical to provider adapters.
- Schema enforced (strict when supported) + post‑validation fallback.
- Determinism and budgets honored; seed forwarded when supported.
- Errors mapped to `ProviderError`/`SchemaError` with retry classification.
- Metrics recorded with `agent_runtime` and streaming performance fields.
- Unit, conformance, and (opt‑in) smoke tests pass.


