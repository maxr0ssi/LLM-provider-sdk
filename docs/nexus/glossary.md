# Glossary (Nexus)

- OA (Orchestrator Agent): deterministic service that coordinates stages/agents.
- Drip-feed: OA-mediated partial results/hints, no agent-to-agent links.
- K×D: replicas per dimension (K) across D dimensions.
- Caps: upper bounds from Lightning or contract applied to dimension scores.
- ScoringContract: intent-driven contract (requirements, thresholds, weights, caps).
- Partial Result: `status=partial` task_result with early_result or arbitration_hint.
- EARLY_RESULT: streaming event for an early dimension stub (score_stub + top_issue).
