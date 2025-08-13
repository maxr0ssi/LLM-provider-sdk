# Decisions (Nexus)

- OA + drip-feed over agent-to-agent links
  - Rationale: central ordering, adaptive K, no side-channels.
- Static local; Intent required before Lightning
  - Rationale: gating + contract alignment for downstream stages.
- Tool-calling local/deterministic only; off by default
  - Rationale: predictability, zero-token overhead, provider-agnostic.
- Responses API for GPT‑5 mini (Intent/Lightning)
  - Rationale: structured outputs via json_schema; lower parse failures.
- Deterministic by default
  - Rationale: CI stability; reproducible scores; reduced variance.
