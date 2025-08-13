# Root Orchestrator Spec (v1)

Purpose: Define responsibilities and components of the Root in A2A V2.

## Responsibilities
- Stage control: Static → Intent → Lightning → K×D → Referee → FINAL
- Policy enforcement: gating, adaptive K, early-exit
- Aggregation: replica merge (trimmed mean), agreement, outlier clipping
- Streaming: emit ordered domain events to TUI/CLI
- Resilience: retries, idempotency, hedged requests, fallbacks to local

## Components
- AgentRegistry: capabilities, health, versions
- TaskRouter: offer dispatching, per-dimension K selection, hedging
- Aggregator: replica→dimension aggregation, confidence/variance
- PolicyEngine: gates, thresholds, model tiering
- StreamingBridge: domain StreamEvent emission and ordering

## Interfaces
- HTTP client for A2A calls (with JWT injection)
- Cache for constitution/contract keyed by prompt hash and version
- Metrics: offers/results/latency/timeout/parse_fail/agreement/referee_rate

## OA Drip-Feed & Blackboard
- OA maintains a blackboard: intent contract, lightning caps, early dim stubs, final verdicts.
- Agents consume immutable snapshots provided in offers; no agent-to-agent reads.
- OA accepts partial results (`status=partial`) and may:
  - Emit DIMENSION_EARLY_RESULT events
  - Compute agreement and trigger early-exit (stop K)
  - Request third replica when ARBITRATION_HINT suggests conflict risk

## Tool-Calling Guidance
- Tools are local, deterministic functions attached to an agent’s Responses call (optional).
- Allowed examples: schema_repair, annotation_dedup, span_quote_check, regex_probe.
- Disallowed in V2: external context fetch; OA must remain deterministic code (no LLM in OA).
