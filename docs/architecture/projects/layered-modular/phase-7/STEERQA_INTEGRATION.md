## SteerQA (Nexus) Integration – Phase 7 Goal and How This SDK Fits

### Purpose
- Explain how the SDK’s Phase 7 “Agents Integrations Runtime” (starting with OpenAI Agents SDK) plugs into SteerQA’s Nexus platform (Root + Agents via A2A).
- Provide a contract-level map: inputs/outputs, streaming events, reliability, and cost reporting for OA to consume.

### SteerQA (Nexus) overview (what it expects)
- Orchestrator (Root) calls stage/dimension agents over A2A v1 (HTTP): `/task_offer` → `/task_result`.
- Streaming v2 events to client: `STATIC_CHECK_COMPLETE`, `INTENT_EXTRACTION_COMPLETE`, `LIGHTNING_COMPLETE`, `REPLICA_COMPLETE`, `DIMENSION_COMPLETE`, `FINAL`.
- Intent/Lightning produce strict JSON (schema‑validated); Dimension agents produce verdicts with scores, annotations, confidence.
- Determinism (seed), budgets (tokens/ms), idempotency, and telemetry are required for stability and audit.

### Phase 7 goal (SDK)
- Add a core Agents Runtime layer that normalizes vendor‑native Agent SDKs (OpenAI first) to the SDK’s provider‑agnostic contracts.
- Users select `runtime="openai_agents"` in `AgentRunner`; OA continues to see the same normalized results, usage, events, and errors.

### High-level flow
```
Client/OA ──► AgentRunner (runtime=openai_agents)
              │
              ├─► Agents Runtime Adapter (OpenAI)
              │     ├─ Map AgentDefinition → OA Agent (instructions, tools, model)
              │     ├─ Run via Runner (agent loop, tool calls)
              │     ├─ Stream deltas → EventManager (typed events)
              │     └─ Enforce schema (strict when supported) + post‑validate
              │
              └─► Normalized AgentResult (content|json, usage, model, elapsed_ms, trace_id)
                         + metrics (ttft, chunks, throughput, cost_usd)
```

### Contracts mapping (OA ↔ SDK)
- Inputs from OA into SDK Agent path:
  - `system`, `user_template`, `variables` → rendered input text; optional tools.
  - `json_schema` → Responses `text.format` (root `additionalProperties=false`), `strict=True` where supported; always post‑validate on completion.
  - `deterministic`, `seed`, `budget.tokens/ms`, `idempotency_key`, `trace_id` → forwarded/ enforced by runtime.
- Output back to OA:
  - `AgentResult.content`: text or validated JSON (for Intent/Lightning structured outputs).
  - `AgentResult.usage`: `{prompt_tokens, completion_tokens, total_tokens, cache_info}`.
  - `AgentResult.model`, `elapsed_ms`, `trace_id`, `provider_metadata`.
  - `AgentResult.cost_usd` (when pricing known) + `cost_breakdown`.

### Streaming mapping (SDK → A2A v1)
- SDK callbacks map to A2A events:
  - `on_start(meta)` → START
  - `on_delta(delta)` → DELTA (normalized text/JSON; JSON dedup assured)
  - `on_usage(usage)` → USAGE (single emission; estimated when needed)
  - `on_complete(result)` → COMPLETE
  - `on_error(error)` → ERROR (typed, retryable classification)
- OA stage events (Streaming v2) are composed at Root from these low‑level callbacks.

### Determinism, budgets, idempotency
- Determinism: clamp params (e.g., temperature), forward `seed` when supported (capabilities-driven).
- Budgets: token/time via reliability layer; can abort or return partials per policy.
- Idempotency: OA supplies `idempotency_key`; SDK dedup/retries handled via reliability managers.

### Cost reporting
- Router/runtime computes exact cost when possible (per‑model pricing) and sets `response.cost_usd` and optional `cost_breakdown` (input/output/cache_savings).
- Streaming path emits usage once on completion; cost computed then (or estimated when usage is aggregated).
- Metrics include `request_cost_usd` for external sinks.

### Observability & external monitoring
- Metrics dimensions: `provider`, `model`, `agent_runtime` (e.g., `openai_agents`), `ttft_ms`, `chunks`, `throughput`, `tools_invoked`, `agent_loop_iters`, `retry_count`, error category.
- Suggested host endpoints (OA side):
  - `/health/agents` – availability of runtimes and creds.
  - `/metrics` – Prom/OTLP; SDK writes to sinks.
  - `/agents/runs/{id}` – run snapshot (request_id, model, ttft, usage, cost, errors), built from SDK metadata.
- Tracing: `trace_id` propagated; vendor trace/run IDs captured in `provider_metadata` for correlation.

### Capability-driven behavior (schema/params)
- Use capability registry for:
  - Structured output support (use Responses `text.format` when available; else post‑validate only).
  - Token field name mapping (`max_tokens` ↔ `max_output_tokens`).
  - Temperature support/constraints (omit or clamp for fixed‑temp models like GPT‑5 mini in schema mode).
  - Seed support.

### Reliability
- Error taxonomy via `ProviderError` with retryable classification (Rate Limit/Timeout/Network/Server/etc.).
- Retries, circuit breakers, and streaming retry (connection/read timeout) are integrated and configurable; `request_id` consistently propagated.

### Minimal OA invocation pattern (conceptual)
```python
# Build SDK AgentDefinition per stage, then:
result = await AgentRunner().run(
    definition,
    variables=vars,
    options={
        "runtime": "openai_agents",
        "streaming": True,
        "deterministic": True,
        "budget": {"tokens": 1500, "ms": 5000},
        "idempotency_key": key,
        "trace_id": trace,
        "metadata": {"strict": True, "responses_use_instructions": True},
        # callbacks: on_start/on_delta/on_usage/on_complete/on_error
    }
)
# Map result to A2A task_result
```

### Risks & mitigations (Phase 7)
- Vendor SDK drift → keep adapter thin; version pin; unit tests for API changes.
- JSON streaming variance → normalized deltas + JSON dedup; finalize usage once.
- Performance overhead → lazy import; JSON handler opt‑in; event pipeline < 1ms.

### What to validate before/after rollout
- Capability flags for targeted models (schema/seed/temp/tokens) correct.
- All providers/paths attach `request_id`, `trace_id` across events/metrics.
- Costs present and correct for known models; metrics include `request_cost_usd`.

### Summary
- Phase 7 makes vendor‑native agent SDKs a first‑class runtime while preserving SDK‑wide invariants.
- SteerQA (Nexus) consumes the same normalized contracts (results, usage, costs, events, errors), with richer metrics for quality and cost accounting.


