

# Orchestration Overview  

Note: This code references ideas outside of this SDK, but it is important for context we understand why this archetecture is being changed.


**How the Orchestrator Agent and Bundle Tools work together — and why**

This document explains the overall approach for running complex evaluations with multiple specialist agents in parallel, why we adopted **bundle tools** (a.k.a. *barrier tools*), and how the **orchestrator agent** consumes the results to reason once over complete, high‑quality evidence.

---

## Why we’re doing this

Traditional “fan‑out then merge” patterns often **collapse multiple agent outputs into a single JSON/text** via naïve rules (last‑write‑wins, field‑wise union, string concat). That loses valuable signal:

- **Conflicts disappear** — we can’t see disagreements between replicates.
- **Uncertainty is hidden** — no distributions or distances to quantify confidence.
- **Math is left to prompts** — deterministic computations (validation, stats) end up in the LLM instead of code.

We want the LLM to **reason once** with the **full evidence** (all K replicate outputs) *plus* a compact, deterministic summary (consensus, disagreements, distances, distributions). That’s what the **bundle tool** provides.

---

## Core concepts

- **Orchestrator agent**  
  A coordinating agent that decides *which* specialist work to run and *when* to use bundle tools. It does not crunch numbers; it consumes **atomic evidence** and produces a final, explained decision.

- **Sub‑agents (specialists)**  
  Focused agents that perform specific checks (e.g., feasibility, clarity). They produce **structured JSON** or well‑formed text for their task.

- **Bundle tool (barrier tool)**  
  A code‑executed barrier that:
  1) **Fans out** K sub‑agent calls in parallel (varying seeds/strategies),
  2) **Validates** each output (schema/quality flags),
  3) Computes **consensus, disagreements, pairwise distance, distributions, confidence**, and optional **early‑stop**,
  4) Returns a single **Evidence Bundle** for the orchestrator to read.

- **Evidence Bundle**  
  A compact object containing **raw replicates** and a **summary** of computed statistics. The orchestrator agent reads this bundle in one turn and justifies its choice, citing disagreements when present.

- **Lint lane (separate path)**  
  Fast, non‑blocking checks that surface nits and guardrails in real time. Lints do not gate evaluate flows; they run with tiny budgets.

---

## End‑to‑end flow

```
User request
   ↓
[ Orchestrator Agent ]
   ├─ decides: replicate‑and‑decide? → yes
   └─ calls → [ Bundle Tool: Feasibility ]
                ├─ run sub‑agent r1 (seed 11) ┐
                ├─ run sub‑agent r2 (seed 23) ├── parallel
                └─ run sub‑agent r3 (seed 47) ┘
                ├─ validate JSONs (schema_uri)
                ├─ compute distances/distributions/consensus
                ├─ early‑stop if dist(r1,r2) ≤ ε
                └─ produce Evidence Bundle
   ↓
Orchestrator reads bundle → reasons once → final decision/report
   ↓
Backend/UI receives progress events + final result
```

**Streaming:** While the bundle tool runs, it emits progress events (e.g., `replicate_done`, `partial_summary`) to the backend so UIs can show **early results**. The orchestrator receives **one atomic bundle** at the end of the tool call.

---

## When to use the bundle tool

Use the bundle tool for **replicate‑and‑decide** tasks where:
- Multiple sub‑agent outputs provide complementary or conflicting evidence,
- Disagreements matter (we must expose them),
- Confidence should be grounded in **computed distances/distributions**,
- Latency/cost benefits from **K=2 + early‑stop K3**.

Examples: feasibility checks, risk triage, policy adjudication, multi‑judge scoring.

For simple text responses: **append‑only** (ordered concat).  
For JSON with exactly one result: **passthrough**.  
For multiple JSONs: **do not merge in the orchestrator** — use a **bundle tool**.

---

## Evidence Bundle (minimal contract)

```json
{
  "meta": { "task": "feasibility", "k": 3, "model": "provider:model@ver", "seeds": [11, 23, 47] },
  "replicates": [
    { "id": "r1", "data": { /* validated JSON */ }, "quality": { "valid": true } },
    { "id": "r2", "data": { /* validated JSON */ }, "quality": { "valid": true } },
    { "id": "r3", "data": { /* may be invalid */ }, "quality": { "valid": false, "errors": ["missing X"] } }
  ],
  "summary": {
    "consensus": { /* field‑wise consensus where unambiguous */ },
    "disagreements": [ { "field": "threshold", "values": [0.6, 0.8] } ],
    "pairwise_distance": [[0,0.18,0.22],[0.18,0,0.27],[0.22,0.27,0]],
    "distributions": { "score": { "mean": 0.63, "stdev": 0.12 } },
    "confidence": 0.74,
    "truncated": false
  }
}
```

**Prompt hint for the orchestrator agent:**  
> Use `replicates[]` as ground evidence; treat `summary` as statistics. If disagreements exist, cite them and justify your choice.

---

## Algorithm notes (replicate‑and‑decide)

- **Parallel K:** Start with **K=2** replicates using diverse seeds/strategies; compute `dist(r1, r2)`.  
- **Early‑stop:** If `dist ≤ ε`, skip K3; otherwise run **K=3** and recompute consensus/metrics.  
- **Distances (per field):**  
  - numeric: normalized absolute difference,  
  - categorical: disagreement flag + Jaccard,  
  - sets/sequences: Jaccard or overlap,  
  - objects: field‑wise comparison with weights.  
- **Confidence (starter):** `confidence = 1 − mean_pairwise_distance` (bounded [0,1]); may weight by `quality` or model tier later.
- **Invalid replicates:** mark `quality.valid=false`; exclude from consensus but **include** in disagreements for transparency.

---

## Budgets, caps, and truncation

- **Per‑replicate ceilings:** tokens and wall‑clock per sub‑agent.  
- **Global bundle budget:** cancels stragglers once confidence/time thresholds are met.  
- **Bundle caps:** `max_fields`, `max_diffs`, `max_bytes`. If exceeded, set `truncated:true` and include counts.  
- **Token discipline:** diff‑encode replicates (base + deltas) and include only **top‑N disagreements**.

---

## Events & streaming (for early UX)

Example event types emitted by the bundle tool to the backend:

- `replicate_started` / `replicate_done` (with usage)
- `partial_summary` (after K=2)  
- `bundle_ready` (final Evidence Bundle)
- `warning` (validation errors, truncation)
- `cancelled` / `timeout`

The orchestrator consumes only the **final bundle**, keeping its prompt compact and atomic.

---

## Tool registration (SDK) and event mapping

- Tools are implemented in the host app (e.g., SteerQA) and registered with the SDK at startup.

```python
# In SteerQA bootstrap
from llm_sdk_core import SDK
from steerqa.tools.feasibility import FeasibilityBundleTool

sdk = SDK(...)
sdk.register_tool(FeasibilityBundleTool)  # name e.g. "feas_bundle"
# Planner decides when the orchestrator agent includes "feas_bundle" in its tool list.
```

- Progress events from tools should map to the SDK's normalized streaming events via `EventManager`:
  - `on_start` (tool run begins), `on_delta` (e.g., replicate_done, partial_summary),
    `on_usage` (usage per replicate or aggregate), `on_complete` (bundle_ready), `on_error`.
  - Tag events with `metadata.source = "feas_bundle_tool"` (or the tool name). Redaction hooks apply before emission.

---

## Metrics: usage and cost aggregation

- The bundle tool must compute and report aggregate usage/cost across its K sub‑agent runs.
- Surface usage per replicate (optional), aggregate usage, and aggregate cost in the final bundle metadata.
- The orchestrator collects these metrics and records them alongside the agent decision for observability.

---

## Responsibilities (at a glance)

| Component           | Responsibilities                                                                 |
|---------------------|-----------------------------------------------------------------------------------|
| Orchestrator agent  | Choose flow; call bundle tools; read bundles; reason once; produce final report. |
| Bundle tool         | Parallelize K calls; validate; compute stats; early‑stop; emit events; return bundle. |
| Sub‑agents          | Produce structured outputs for their specialty.                                   |
| Backend/UI          | Display progress and partials; render final decision with cited disagreements.    |
| Lint lane           | Fast, non‑blocking hints/guardrails; separate budgets and path.                   |

---

## Versioning & reproducibility

- **Schema version** in `meta` (e.g., `feasibility.v1`) governs the shape of `replicates[].data` and `summary`.  
- **Seeds/model IDs** recorded in `meta` for exact replay.  
- **Determinism:** where the runtime supports seeds, pass them through; where not supported, document as no‑op.

---

## Security & redaction

- Redact secrets/PII before events leave the process.  
- Field‑level controls: only include data necessary for the orchestrator to reason; avoid dumping raw histories where structured extracts suffice.

---

## FAQ

**Why not let the orchestrator merge JSONs?**  
Because merges are **lossy** and hide conflicts/uncertainty. We want the agent to see all evidence plus deterministic stats.

**Why run math in code instead of the LLM?**  
Validation and statistics are **deterministic** and cheaper in code; the LLM should focus on judgment and explanation.

**Why a barrier tool instead of calling sub‑agents directly from the orchestrator?**  
A barrier delivers **atomic context** (all K results + stats) in a single turn, reduces token churn, and preserves determinism.

---

## Configuration knobs (per task)

- `k` (default 3), `epsilon` (default 0.2), `seeds` (e.g., `[11,23,47]`)  
- `schema_uri` (validation)  
- `bundle_limits` `{max_fields, max_diffs, max_bytes}`  
- Per‑replicate `{tokens, seconds}` ceilings and a **global** budget

---

## Glossary

- **Replicate:** one sub‑agent run with a particular seed/strategy.  
- **Evidence Bundle:** atomic object with raw replicates + computed stats.  
- **Barrier tool:** code‑executed function that produces an Evidence Bundle.  
- **ε (epsilon):** early‑stop threshold on pairwise distance.  
- **Lint lane:** separate, fast path for hints/guardrails that never blocks the evaluation.