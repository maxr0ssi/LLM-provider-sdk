# Orchestration Dev Phases

## Standard Contracts (apply across phases)

- Use `AgentRunner` with `runtime="openai_agents"` for all sub-agent calls.
- Enforce budgets, timeouts, retries, and cancellation policies consistently.
- Streaming events tagged with `source=agent_name`.
- Usage and cost aggregation per-agent and global.
- Minimal observability: request_id, trace_id, elapsed_ms, usage, cost.
- Security & redaction: redact sensitive data in logs and events.

- Tool registry (SDK-level): the SDK exposes `register_tool(tool: ToolDef) -> None`; tools are implemented in the host app (e.g., SteerQA) and registered at startup.

## Phase M0 — MVP

- Static registry of sub-agents with `SubAgentSpec`.
- Parallel execution with `asyncio.Semaphore(max_parallel)`.
- Per-agent timeouts enforced; budgets are validated post-run (no token division in M0).
- Append-only text aggregation; JSON passthrough only when single JSON present.
- Streaming multiplex with tagged events.
- Usage and cost summation.
- Minimal error aggregation; no fallback.
- Docs:
  - Add `docs/orchestration/overview.md` (add event schema and tool registry API); link from `docs/INDEX.md` and `README.md`.

## Phase M0.5 — Barrier Tool & Evidence Bundle (SteerQA owned)

- Replace naive merge in replicate-and-decide flows with a Barrier Tool that runs K sub-agents in parallel, validates JSONs, computes consensus/disagreements/distances/distributions/confidence, supports early-stop by ε, and returns a single Evidence Bundle for the agent to reason over once. SDK remains domain-neutral; SteerQA implements the tool and registers it at startup.
  - Metrics: the tool reports aggregate usage/cost across K runs; the orchestrator surfaces these alongside the final bundle.
  - Acceptance: planner chooses subset; orchestrator consumes a single Evidence Bundle from the tool; retries only on retryable errors; metrics include per-agent timings.

## Phase M1 — Planner, JSON merge, reliability & idempotency

- Planner:
  - Rule-based or LLM-generated task graph.
  - Dynamic sub-agent selection.
- Code:
  - Expose `MergeStrategy` interface in `merger.py`:
    - Default remains JSON passthrough (single-object only). Applications may register a merge plugin and handle schema validation at the app level; the SDK does not ship a multi-JSON merge.
  - Retry manager with bounded retries and circuit breakers.
  - Idempotency key passthrough.
- Acceptance criteria:
  - Planner dynamically selects sub-agents; `MergeStrategy` interface available with default JSON passthrough; reliability bounded and observable; idempotency semantics enforced.