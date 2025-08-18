# Orchestrator Agents — Phased Implementation Plan (Dev Guide)

This plan turns the high-level design in `orchastration-plan.md` into concrete, incremental phases for developers. It lists exact modules to add/change, acceptance criteria, and test/doc updates. All agent executions must use `AgentRunner(..., runtime="openai_agents")` — no fallbacks.

Notes:
- Domain-neutral: terminology and APIs are generic; any role names in examples are illustrative only (e.g., “specialist”, “scorer”).
- MVP runtime pinning: Phase M0 pins `runtime="openai_agents"` with no fallback. The runtime remains pluggable for M1+ via adapters.

## Standard Contracts (apply across phases)

- Result typing (SDK-level):
  - content: str | dict
  - usage: normalized dict (prompt/completion/total tokens; cache info when available)
  - status: "accepted" | "running" | "succeeded" | "failed" | "partial"
  - error?: { code: str, message: str, provider?: str, retriable?: bool }
  - Optional discriminator for payload style: { type: "json" | "text" | "tool", data: Any, schema_uri?: str }

- Determinism semantics:
  - Always pass seed when provided; if provider lacks support, treat as no-op and emit a warning (log + event).

- Idempotency semantics:
  - Same idempotency_key + same payload → return stored result (upsert behavior).
  - Same idempotency_key + different payload → reject with conflict (HTTP 409 equivalent).

- Streaming event schema (minimal):
  - on_start: { provider, model, request_id?, metadata? }
  - on_delta: { source?: agent_name, delta: str | dict, is_json?: bool, chunk_index }
  - on_usage: { provider, model, usage: dict, is_estimated: bool, confidence?: float }
  - on_complete: { provider, model, total_chunks, duration_ms, final_usage?, metadata? }
  - on_error: { provider, model, error: { code, message, retriable? } }

- Security & redaction:
  - Provide a pre-emit redaction hook for events/logs; callable can be injected by host app.

- Tool registry (SDK-level):
  - Tool registry (SDK-level): the SDK exposes `register_tool(tool: ToolDef) -> None`; tools are implemented in the host app (e.g., SteerQA) and registered at startup.

## Phase M0 — MVP (Parallel sub-agents, tagged streaming, append-only)

- Goals:
  - Fan-out/fan-in orchestration over a static list of focused sub-agents.
  - Run sub-agents in parallel; collect and append results (no multi-JSON merge); surface early streaming.
  - Aggregate usage and compute total cost; minimal metrics.

- Code: add new orchestration module (no core refactors)
  - Add directory: `steer_llm_sdk/orchestration/`
    - orchestrator.py — main coordinator (fan-out/fan-in). Responsibilities:
      - Accept request, registry: list[SubAgentSpec], options: OrchestrationConfig, optional EventManager.
      - Launch sub-agents in parallel via asyncio.Semaphore(max_parallel) + asyncio.gather(return_exceptions=True).
      - For each sub-agent: call AgentRunner().run(definition, variables, {"runtime": "openai_agents", ...}) with per-agent budgets/timeouts/determinism propagated.
      - Aggregate AgentResult objects: sum usage; compute cost via existing calculate_exact_cost if usage present.
      - Produce OrchestrationOutput with content, usage_total, per_agent, cost_total_usd, elapsed_ms, status, errors?.
    - registry.py — definitions for SubAgentSpec and helper lookups.
    - options.py — OrchestrationConfig model (max_parallel, budgets, deterministic, streaming, retries, timeouts_ms, trace_id, request_id, redactor_cb?).
    - merger.py — content policy:
      - Text: append-only (ordered concat by priority or completion time).
      - JSON: deprecated for multi-JSON; only passthrough when exactly one JSON present (no multi-JSON merge).
    - streaming.py — event fan-out:
      - Wrap caller EventManager; tag on_start/on_delta/on_usage/on_complete/on_error with source=agent_name in metadata.
      - Preserve per-source ordering; apply redaction hook before emit.
    - errors.py — orchestration-level exceptions (e.g., SubAgentFailed, BudgetExceeded, ConflictError).
  - No edits to: AgentRunner, OpenAI adapter, providers. Orchestrator only composes them.

- Tests:
  - New unit tests under `tests/unit/orchestration/`:
    - test_parallel_execution.py — runs 2–3 mocked sub-agents in parallel; verifies concurrency and completion.
    - test_streaming_tagging.py — validates source=agent_name tagging and interleaving; per-source ordering preserved.
    - test_usage_aggregation.py — sums per-agent usage into usage_total and computes cost_total_usd.
    - test_timeouts_and_cancellation.py — per-agent timeout cancels long task; others complete.
  - Integration smoke under `tests/integration/orchestration/` using lightweight fakes.

- Docs:
  - Add `docs/orchestration/overview.md` (add event schema and tool registry API); link from `docs/INDEX.md` and `README.md`.
  - Note strict “no fallback” and MVP pinning; SDK is domain-neutral.

- Acceptance criteria:
  - Orchestrator returns final answer with combined usage/cost; streams early deltas tagged by source; exposes statuses and error payloads.
  - Text is append-only; multi-JSON merge is not performed (single-JSON passthrough only).
  - All sub-agent calls go through AgentRunner(..., runtime="openai_agents").

## Phase M0.5 — Barrier Tool & Evidence Bundle (SteerQA owned)

- Goals (replicate-and-decide flows, e.g., feasibility):
  - Replace naive merge with a Barrier Tool that:
    1) runs K sub-agents in parallel, 2) validates JSONs (schema_uri),
    3) computes consensus/disagreements/distances/distributions/confidence,
    4) early-stops K3 when r1 vs r2 ≤ ε, 5) returns a single Evidence Bundle to the agent.

- Ownership & repos:
  - SDK: keep orchestrator/concurrency/streaming neutral; expose tool registry surface only.
  - SteerQA app: implements Barrier Tool, metrics, schemas, and planner/routing; registers the tool with SDK at startup.

- SDK surface (pass-through only):
  - Option values (owned by SteerQA) may be carried through: `k`, `epsilon`, `schema_uri`, `seeds`, `bundle_limits {max_fields,max_diffs,max_bytes}`, `global_budget`.
  - Streaming: allow tool-level progress events to backend (`source="feas_bundle_tool"`); redaction hook applied.

- Evidence Bundle (contract, minimal):
  ```json
  {
    "meta": { "task":"feasibility", "k":3, "model":"provider:model@ver", "seeds":[11,23,47] },
    "replicates": [
      {"id":"r1","data":{...},"quality":{"valid":true}},
      {"id":"r2","data":{...},"quality":{"valid":true}},
      {"id":"r3","data":{...},"quality":{"valid":false,"errors":["missing X"]}}
    ],
    "summary": {
      "consensus": {...},
      "disagreements": [{"field":"threshold","values":[0.6,0.8]}],
      "pairwise_distance": [[0,0.18,0.22],[0.18,0,0.27],[0.22,0.27,0]],
      "distributions": {"score":{"mean":0.63,"stdev":0.12}},
      "confidence": 0.74,
      "truncated": false
    }
  }
  ```

- Tests (SteerQA):
  - `test_barrier_runs_k_parallel_and_bundles()`
  - `test_bundle_schema_and_quality_flags()`
  - `test_early_stop_by_epsilon()` (r1 vs r2 ≤ ε skips K3)
  - `test_budget_caps_and_cancellation()` (per-replicate + global)
  - `test_backend_streaming_from_tool()` (progress events; per-source ordering)
  - `test_bundle_truncation_metadata()` (caps → `truncated:true`)

- Acceptance:
  - Orchestrator agent calls the Barrier Tool once for feasibility flows.
  - Tool returns a valid Evidence Bundle; agent receives one atomic payload.
  - Backend receives progress events while the tool runs; early-stop and caps enforced.
  - Acceptance: planner chooses subset; orchestrator consumes a single Evidence Bundle from the tool; retries only on retryable errors; metrics include per‑agent timings.

## Phase M1 — Planner, AggregationPolicy, reliability & idempotency

- Goals:
  - Introduce a simple planner to select sub-agents per request.
  - AggregationPolicy: keep default as append-only text and single-JSON passthrough; expose optional app-level aggregation plugin (SDK ships none). Wire bounded retries and circuit breakers per sub-agent.
  - Pass through idempotency key; enforce conflict semantics; propagate tracing.

- Code:
  - Add planner.py in `steer_llm_sdk/orchestration/`:
    - `Planner` interface and RuleBasedPlanner (match on request attributes → sub-agent subset/ordering).
  - Expose `AggregationPolicy` extension in `merger.py` (or a dedicated aggregation module):
    - Default remains append-only text and JSON passthrough (single-object only). Applications may register an aggregation plugin and handle schema validation at the app level; the SDK does not ship a multi-JSON merge.
  - Reliability hooks:
    - In orchestrator.py, wrap each sub-agent run with existing RetryManager (bounded attempts, retryable errors only) and optional provider circuit breaker (map breaker key to model/provider).
  - Idempotency & tracing:
    - Thread idempotency_key, trace_id, request_id into each AgentRunner.run invocation; surface in OrchestrationOutput.

- Tests:
  - test_planner_selection.py — planner picks correct subset/order given request metadata.
  - test_aggregation_policy_plugin.py — optional app-level aggregation plugin is invoked when configured.
  - test_retries_and_breakers.py — retry only on retryable; breaker trips after threshold.
  - test_idempotency_trace_passthrough.py — keys propagate and deduplicate; conflict on changed payload.

- Docs:
  - `docs/orchestration/technical-design.md` — planning flow, aggregation policy (append-only/passthrough) and optional plugin, reliability/idempotency policy.

- Acceptance criteria:
  - Planner dynamically selects sub-agents; `AggregationPolicy` extension available with default append-only/passthrough; reliability bounded and observable; idempotency semantics enforced.

## Phase M2 — Quality signals, early stop, synthesizer pass

- Goals:
  - Confidence/quality signals to allow early stop when “good enough”.
  - Optional synthesizer agent to polish/compose final output.
  - Better budget control (global ceilings).

- Code:
  - Extend options.py with early_stop policy (e.g., confidence threshold, quorum count).
  - orchestrator.py:
    - Global budget (tokens/time). Cancel remaining tasks when threshold reached or early-stop condition satisfied.
    - Optional synthesizer step: call a designated synth_agent (via AgentRunner) with collected partials to produce final.
  - merger.py:
    - Add deduplication heuristics for text; keep simple and deterministic; expose merge plug-in interface (textual/semantic/structural metrics).

- Tests:
  - test_early_stop_by_confidence.py — stops remaining work when threshold reached.
  - test_synthesizer_pass.py — synthesizer composes partials into improved final answer.
  - test_global_budget_ceiling.py — cancels when cost/time ceiling hit.

- Docs:
  - Update technical design with early-stop and synthesizer patterns and caveats.

- Acceptance criteria:
  - Demonstrated latency/cost reduction with early stop on simple tasks; optional synthesizer improves quality.

## Phase M3 (Optional) — OA handoffs, lightweight session memory, tracing hooks

- Goals:
  - Expose controlled OpenAI Agents SDK handoffs (agent-calls-agent inside runtime) behind feature flags.
  - Add ephemeral session memory per orchestrated request.
  - Enrich tracing hooks (still lightweight pre-prod).

- Code:
  - orchestrator.py:
    - Feature-flagged path to instruct sub-agents to use OA handoffs where applicable (no fallback; still via openai-agents).
  - state.py:
    - Ephemeral per-request memory structure (inputs, partials, tool results, decisions).
  - Tracing:
    - Optional callbacks to emit per-step spans; keep minimal fields (agent, start/end, status, usage).

- Tests:
  - test_handoffs_flagged_path.py — ensure handoffs only when flag set; otherwise top-level orchestration.
  - test_session_memory_scoping.py — memory scoped to a single orchestrated run.

- Docs:
  - Add `docs/orchestration/usage.md` examples for handoffs flag and memory.

- Acceptance criteria:
  - Handoffs work only when enabled; tracing fields present; orchestrator remains provider-agnostic at core.

## Cross-Cutting Requirements

- Capability-driven policy:
  - Reuse ProviderCapabilities for temperature/seed/token field mapping; do not hardcode model checks.
- Determinism:
  - Clamp params; pass seed where supported; warn on no-ops.
- Usage & cost:
  - Prefer provider-reported usage; otherwise estimate consistently with existing aggregators; compute cost centrally.
- Observability (minimal):
  - Record elapsed_ms, per-agent usage, total usage/cost; propagate request_id/trace_id.
- Security:
  - Tools and sub-agents remain deterministic by default; redaction hooks in streaming/logging; document any side-effects explicitly.

## File/Module Reference

- Existing (used, not modified in M0):
  - `steer_llm_sdk/agents/runner/agent_runner.py`
  - `steer_llm_sdk/integrations/agents/openai/adapter.py`
  - `steer_llm_sdk/integrations/agents/streaming.py`
  - `steer_llm_sdk/core/routing/selector.py` (cost calc)
  - `steer_llm_sdk/core/capabilities/*`
  - `steer_llm_sdk/streaming/*` (EventManager, StreamAdapter)

- New (to be added by phase):
  - M0: `steer_llm_sdk/orchestration/{orchestrator.py, registry.py, options.py, merger.py, streaming.py, errors.py}`
  - M1: `steer_llm_sdk/orchestration/planner.py` (+ extensions in aggregation/reliability wiring)
  - M2: updates to `options.py`, `orchestrator.py`, `merger.py`
  - M3: `steer_llm_sdk/orchestration/state.py` (+ optional handoffs path)

## Documentation Updates

- M0: `docs/orchestration/overview.md` (add event schema); link from `README.md` and `docs/INDEX.md`.
- M1: `docs/orchestration/technical-design.md` (planner, aggregation policy, reliability, idempotency).
- M2: extend design docs (early-stop, synthesizer, budgets, aggregation plug-ins).
- M3: `docs/orchestration/usage.md` (handoffs, memory, tracing hooks).

## Test Plan Summary

- Add `tests/unit/orchestration/*` and `tests/integration/orchestration/*` per phase.
- Ensure streaming tests validate source tagging and interleaving; per-source ordering preserved.
- Keep tests aligned with contracts (normalized results/events, async generators).

---

Implementation should proceed phase-by-phase; avoid touching provider adapters and AgentRunner unless strictly necessary. Orchestrator composes existing primitives and enforces the “no fallback” policy by always executing sub-agents via the OpenAI Agents runtime.
