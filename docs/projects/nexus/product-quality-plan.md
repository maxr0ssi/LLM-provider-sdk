# SteerQA 2.0 — Product Quality Plan (Agent‑Mesh, no MCP)

This plan complements `overview.md` with a product‑oriented roadmap focused strictly on evaluation quality (ignore DB, auth, rate limiting). It specifies the pipeline, contracts, orchestration policies, quality enhancements, metrics, UX, rollout, and risks.

## 1. Objectives (quality only)

- Reliable, calibrated scores across dimensions with actionable annotations
- Early, trustworthy streaming signals per stage/dimension
- Robustness to prompt phrasing, adversarial patterns, and long inputs
- Deterministic modes for CI and reproducibility

Non‑goals: persistence, auth, quotas, billing, external context (MCP) — deferred.

## 2. Architecture and Pipeline

Authoritative stage order (Root orchestrates):

0) Static Checks (local Python)
- Purpose: low‑cost gating; auto‑stop on critical; can be skipped
- Output: `StaticCheckResult[]`, `gating_decision {continue|stop}`
- Stream: `STATIC_CHECK_COMPLETE`

1) Intent Agent (A2A)
- Purpose: extract objectives/requirements; synthesize `ScoringContract`
- Output: `IntentPacket`, `ScoringContract`
- Stream: `INTENT_EXTRACTION_COMPLETE`

2) Lightning Agent (A2A)
- Purpose: fast caps and early classification using `ScoringContract`
- Output: `caps_applied`, optional early gate
- Stream: `LIGHTNING_COMPLETE`

3) Dimension Agents K×D (A2A, replicas)
- Purpose: per‑dimension scoring with replica diversity
- Output: `ReplicaVerdict` → aggregate to `DimensionVerdict`
- Stream: `REPLICA_COMPLETE` → `DIMENSION_COMPLETE`

4) Referee Agent (A2A)
- Purpose: resolve conflicts/low agreement across dimensions
- Output: `referee_resolution`

5) Aggregate → FINAL
- Purpose: combine dimension results into final score and pass/fail
- Stream: `FINAL`

### Streaming (unchanged client contracts)
- Events (append‑only): `STATIC_CHECK_COMPLETE`, `INTENT_EXTRACTION_COMPLETE`, `LIGHTNING_COMPLETE`, `REPLICA_COMPLETE`, `DIMENSION_COMPLETE`, `FINAL`
- Ordering: `sequence_id` global + per‑dimension `dimension_seq`

## 3. A2A Contracts v1 (quality‑relevant)

Envelope (Root → Agent and Agent → Root):
- `version`, `message_type`, `task_id`, `trace_id`, `issued_at`, `ttl`, `idempotency_key`, `agent_version`

Intent Offer (Root → Intent):
```json
{
  "version": "1.0",
  "message_type": "task_offer",
  "task_id": "intent-7421",
  "prompt": "…",
  "hints": {"static_findings": []},
  "policy": {"max_latency_ms": 2000}
}
```

Intent Result (Intent → Root):
```json
{
  "task_id": "intent-7421",
  "intent_packet": {
    "objective": "…",
    "requirements": [{"id": "REQ-1", "text": "…", "must": true}],
    "constraints": [{"id": "CON-1", "text": "…"}],
    "focus_aspects": ["role", "audience"]
  },
  "scoring_contract": {"schema_version": "1.0", "dimension_thresholds": {"clarity": 75}},
  "confidence": 0.86
}
```

Dimension Offer (Root → Dim Agent):
```json
{
  "task_id": "clarity-9843",
  "prompt": "…",
  "scoring_contract": {"schema_version": "1.0"},
  "dimension": "clarity",
  "dimension_cap": 75,
  "k_replicas": 3,
  "run_id": "r1",
  "seed": 1
}
```

Replica Result (Dim Agent → Root):
```json
{
  "task_id": "clarity-9843",
  "verdict": {
    "dimension": "clarity",
    "run_id": "r1",
    "score": 58,
    "annotations": [],
    "confidence": 0.72
  },
  "elapsed_ms": 812,
  "model": "gpt-4.1-mini"
}
```

## 4. Root Orchestration (quality policies)

- Gating: stop on Static critical; Intent required (unless explicitly skipped) else fallback contract with lower confidence weight
- Adaptive K×D: per‑dimension K based on historical variance; early‑exit on agreement
- Replica diversity: varied seeds/temps/templates within safe bounds
- Aggregation: per dimension use trimmed mean with outlier clipping; confidence‑weighted merge; expose agreement metric
- Referee triggers: low agreement or cross‑dimension contradictions
- Caching: constitution + contract by `prompt_hash + schema_version`

## 5. Quality Enhancements (near‑term, no MCP)

1) Prompt Taxonomy Classifier → adapt weights/criteria per task type
2) Annotation Critic → validate spans/causal chains/betterprompts; fix or down‑weight
3) Test‑Time Augmentation (2–3 paraphrases) → aggregate for stability
4) Calibration Anchors → small gold set + run‑time scale alignment
5) Adversarial Probe Agent → lightweight jailbreak/heuristic probes
6) Robust Aggregation → trimmed mean/median‑of‑means; expose agreement and uncertainty bands
7) Re‑score Top Suggestion → verify betterprompt actually improves score

## 6. Metrics and Acceptance

- Online: per‑dimension success/parse‑fail/timeout, p50/p95 latency, cost tokens, agreement %, referee rate, caps applied, streaming first‑signal time
- Offline (gold set): Kendall/Spearman vs human, per‑dimension calibration curves, inter‑run stability (seeded), adversarial resilience
- CI gates: parse‑fail < 0.5%, agreement ≥ threshold on core dims, stability ±2 points across seeded reruns

## 7. UX (quality signals)

- TUI: stage timeline with gates, contract preview, caps applied, agreement/confidence badges, replica counts
- CLI: `--plan` preview, `--deterministic`, `--budget <ms|tokens>`, `--skip <stage>`
- Output JSON v2: include `scoring_contract_ref`, `agreement`, `caps_applied`, `provenance`

## 8. Phased Rollout (quality milestones)

Phase 1 (weeks 1–3)
- A2A v1 envelopes & Agent SDK
- Static (local) gating, Intent Agent + `ScoringContract`
- Clarity Agent with K×D + trimmed aggregation + agreement metric
- Streaming additions for Static/Intent/Lightning

Phase 2 (weeks 4–6)
- Structure/Feasibility/Safety Agents; Lightning Agent
- Referee Agent; adaptive K; early‑exit; caching
- Annotation Critic + Re‑score Top Suggestion

Phase 3 (weeks 7–8)
- Taxonomy Classifier; TTA; Calibration Anchors
- Adversarial Probe; robust aggregation polish; acceptance metrics in CI

## 9. Risks (quality‑only) and Mitigations

- JSON parse failures → strict schemas, agent self‑check, critic repair, fallback
- Low agreement → increase K or trigger referee; expose uncertainty bands
- Over‑caps from Lightning → cap audits; contract‑consistent enforcement
- Template drift across models → anchors, nightly calibration, seeded CI
- Long prompts → chunking/sectional analysis in dimension agents (v2.1)

---

This plan preserves current templates and TUI contracts while raising evaluation quality via Intent‑first contracts, replica‑aware aggregation, and targeted robustness features — all achievable before MCP integration.

## 10. MVP Mode (token-thrifty defaults)

- Stages
  - Static: required (zero-token gates)
  - Intent: required (cheap model, concise schema)
  - Lightning: enabled by default (cheap model; caps only)
  - Dimensions: default dims=[clarity,structure,feasibility], K=2, early-exit on small disagreement; referee off (auto-trigger only on large gap)
  - Streaming: stage events only; optional EARLY_RESULT per dim

- Determinism and budgets
  - deterministic=true, temperature<=0.1, fixed seeds if supported
  - budget.tokens and budget.ms per evaluation; enforce early-exit when budgets hit
  - caching: constitution+contract keyed by prompt hash

- Aggregation & agreement (no tokens)
  - median-of-2 or trimmed-mean; agreement = |r1−r2|; confidence = 1−(agreement/100)

- Calibration/proxies (no tokens)
  - piecewise mapping per dimension (small gold set), affine normalization
  - contract consistency checks, regex probes, strict annotation schema validation

- CLI/API flags (examples)
  - `--mode mvp` `--dims clarity,structure,feasibility` `--k 2` `--deterministic`
  - `--budget tokens=1500,ms=5000` `--no-referee` `--stream stage`

- SLOs (MVP)
  - P95 latency < 5s; parse-fail < 0.5%; stability delta ≤ 2 points (deterministic)
  - first-stage signal < 1.5s; stage completeness streamed in order

## 11. Pre‑production Readiness Checklist (lean)

- Scope freeze (MVP)
  - Stages: Static (req) → Intent (req) → Lightning (on) → Dims [clarity,structure,feasibility], K=2, Referee off (auto on large gap)
  - Deterministic default; budgets: tokens≤1500, p95≤5s

- Contracts (freeze)
  - JSON schemas: IntentPacket, ScoringContract, Lightning caps, Dimension verdict (with annotations), Referee (optional later)
  - A2A v1: envelopes + `status=partial|final` (early_result, arbitration_hint)
  - Streaming v2: STATIC/INTENT/LIGHTNING/DIMENSION_EARLY_RESULT?/DIMENSION/FINAL

- OA policy knobs (defaults)
  - Early‑exit when |r1−r2| ≤ 8
  - Third replica only if arbitration_hint.conflict_risk ≥ 0.7
  - Referee disabled by default; enable if |r1−r2| ≥ 20 or cap_violation risk

- Provider & SDK
  - Use GPT‑5 mini via Responses API for Intent/Lightning; fallback to 4.1‑mini
  - SDK supports: response_format JSON schema, streaming, capability registry; no Steer logic
  - AgentDefinition/Runner ready; tool‑calling off by default (local deterministic only when enabled)

- Calibration & proxies (no tokens)
  - Piecewise per‑dim map + affine normalization (v1); span‑quote equality; annotation dedup; score‑annotation consistency rule

- Minimal tests
  - Schema conformance per stage
  - E2E happy path + parse‑fail handling
  - Deterministic run stability (Δ ≤ 2 points)

- Feature flags / rollout
  - evaluation.mode=mvp; drip_feed.enabled=false (default)
  - provider.intent=openai:gpt‑5‑mini (overrideable), deterministic=true
  - Hybrid deployment allowed; off by default


