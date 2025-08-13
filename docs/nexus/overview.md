Steer QA 2.0 — Agent-Mesh Refactor Proposal

A move from threaded workers to an open, protocol-driven evaluator fabric

⸻

0 · Executive summary

Today (POC)	Tomorrow (Mesh)
Monolithic FastAPI service; thread-based worker pool	Root orchestrates Stage/Dimension-Agents over A2A (agent-to-agent) protocol
Static checks coupled to evaluators	Static runs locally (Python) for fast gating before agents
No intent-driven scoring contract	Intent-Agent produces a ScoringContract consumed by Lightning & Dimensions
Web-socket TUI streams only after all dimensions finish	Streaming at each stage: STATIC/INTENT/LIGHTNING/REPLICA/DIMENSION/FINAL
Tight coupling : one codebase, one model set	Model & infra per dimension; hot-swap, autoscale, mixed vendors

The refactor keeps every prompt, schema, and LLM-SDK call intact. We simply wrap workers as micro-agents and route messages with A2A.

⸻

Specs index (read first)
- A2A protocol: `protocol-a2a-v1.md`
- Streaming events: `streaming-v2.md`
- Orchestrator: `orchestrator-spec.md`
- SDK usage: `agent-sdk-guide.md`
- Intent contract: `intent-contract.md`

⸻

1 · What stays the same

/templates
    lightning_system.py
    dimension_system.py
    referee_system.py
/scoring_engine/llm_sdk   (Claude, GPT, 4.1-mini wrappers -- testing GPT 5 mini as well !)
/tui                      (websocket frontend)
/json_schemas

	•	Prompt text, scoring ladder, JSON parsing code
	•	Streaming callback logic (token deltas → websocket)
	•	Model selection flags (model="o4-mini", temperature=0.1)

⸻

2 · What changes (Phase 1 – A2A mesh)

root_evaluator/
    orchestrator.py   <-- hub; issues HTTP offers
agents/
    clarity/
        main.py       <-- exposes /task_offer
        manifest.json
    structure/
    feasibility/
    safety/
    lightning/
    referee/

┌───────── Client / CLI ─────────┐
│ websocket                     │
│  (progress events)            │
└────────┬──────────────────────┘
         │     A2A /task_offer (HTTP+JWT)
         ▼
  ┌───────────────────────────┐
│ Root-Evaluator-Agent      │
├───────────────────────────┤
│ 1. static (local)        │
│ 2. intent-agent          │
│ 3. lightning-agent       │
│ 4. parallel dim-agents   │
│ 5. referee-agent         │
  └───────────────────────────┘
      ▲               ▲
      │ A2A           │ A2A
┌─────┴─────┐     ┌───┴────────┐
│ dim-agent │…    │ referee-A. │
└───────────┘     └────────────┘

	•	All agent calls are HTTP POST /task_offer; results come back as JSON.
	•	Each Dimension-Agent, after finishing its LLM call, 1) posts the verdict to Root, 2) emits a single websocket “dimension_complete” event so the TUI shows live insights.

⸻

3 · Data-flow (macro)

Client
  │  /evaluate(prompt) ─────────────────────────────────────────────► Root
  │  ◄── websocket "START"
Root
  │─► Static (local)  (syntax, length) ──► ok? (gate)
  │   ◄── websocket "STATIC_CHECK_COMPLETE"
  │─► Intent-Agent (contract) ──────────► ScoringContract JSON
  │   ◄── websocket "INTENT_EXTRACTION_COMPLETE"
  │─► Lightning-Agent (caps) ──────────► caps JSON
  │   ◄── websocket "LIGHTNING_COMPLETE"
  │─► ┌ Parallel Fan-out ┐
  │   │ clarity-Agent    │
  │   │ structure-Agent  │
  │   │ …                │
  │   └──────────────────┘
  │◄── 7× dim results
  │─► Referee-Agent  (all results)
  │◄── verdict / fallback?
  │   websocket stream events: REPLICA_COMPLETE, DIMENSION_EARLY_RESULT (optional), DIMENSION_COMPLETE
  │  ◄── websocket "FINAL"
Client

All communication root ⇄ agents is A2A. No agent-to-agent side-channels.

⸻

4 · Streaming strategy (micro)

Events are append-only and ordered by `sequence_id` (global) and `dimension_seq` (per-dimension).
Core events: `STATIC_CHECK_COMPLETE`, `INTENT_EXTRACTION_COMPLETE`, `LIGHTNING_COMPLETE`, `REPLICA_COMPLETE`, `DIMENSION_COMPLETE`, `FINAL`.
Token updates are optional (`TOKEN_UPDATE`) and throttled. No chunk-level spam.
dim-agent::LLM stream
    ├─ collects token deltas internally
    └─ once parseable JSON ready:
          1) POST to Root /task_result
          2) Root emits `REPLICA_COMPLETE`; aggregates to `DIMENSION_COMPLETE`

Note: OA may accept partial results (`status=partial`) for EARLY_RESULT and ARBITRATION_HINT to drive adaptive K; see `streaming-v2.md` and `protocol-a2a-v1.md`.

The user sees early insights at each stage, then replicas, then dimension results, then final.

⸻

5 · Quality policies (evaluation)

- Adaptive K×D: choose K per dimension by historical variance; early‑exit on agreement
- Replica diversity: vary seed/temperature safely for robustness
- Aggregation: trimmed mean with outlier clipping; expose agreement and confidence
- Referee triggers: low agreement or cross‑dimension contradictions
- Caching: reuse constitution and scoring contract by prompt hash + schema version

⸻

6 · Protocol snippets

Envelope fields (both directions): `version`, `message_type`, `task_id`, `trace_id`, `issued_at`, `ttl`, `idempotency_key`, `agent_version`.

POST /task_offer (Intent)
{
  "version": "1.0",
  "message_type": "task_offer",
  "task_id": "intent-7421",
  "prompt":    "…",
  "hints": {"static_findings": []}
}

POST /task_offer (Dimension)
{
  "version": "1.0",
  "message_type": "task_offer",
  "task_id": "clarity-9843",
  "prompt":    "…",
  "scoring_contract": {"schema_version": "1.0"},
  "constitution": {...},
  "dimension": "clarity",
  "dimension_cap": 75,
  "k_replicas": 3,
  "run_id": "r1",
  "seed": 1
}

A2A task result (back to Root)

200 OK
{
  "task_id": "clarity-9843",
  "verdict": { "dimension":"clarity", "run_id":"r1", "score":58, "annotations":[], "confidence":0.72 },
  "elapsed_ms": 812,
  "model": "gpt-4.1-mini"
}

JWT headers carry auth; optional progress endpoint is used only for real-time UX.

⸻

7 · Phase 2 preview — MCP enrichment

dim-agent
   ├─ needs SEC-LLM-v3?
   │    └─► mcp /context-query(policy:SEC-LLM-v3)
   │    ◄── chunk(s)
   └─ build augmented prompt

Vertical fetch; does not change A2A flow.

⸻

8 · Deployment view

               +-------------------------------+
               |  k8s / Cloud Run namespace    |
               |                               |
     +---------+ root-evaluator  (1-3 pods)    |
     |         +---------------+--------------+
     |                         |
+----+----+  (6-10 pods autoscaled per agent)  |
| clarity |  | structure | … | referee |       |
+---------+  +-----------+---+---------+       |
               +-------------------------------+

Agents scale independently; HPA on CPU/memory or queue length.

⸻

9 · Step-by-step implementation schedule

Week	Deliverable	Detail
1	Repo clean + docs	prune demo code; architecture README & diagrams
2	Intent-Agent + contract	FastAPI /task_offer, contract schema, tests
3	Clarity-Agent live	copy worker, FastAPI /task_offer, dockerfile, manifest.json
4	Root orchestrator HTTP calls	replace threadpool with aiohttp requests; fallback to local call in dev
5	Remaining dimension agents	structure, specificity, feasibility, safety
6	Referee-agent + JWT auth	Google Cloud OAuth proxy; signed task results
7	Streaming v2 additions	emit STATIC/INTENT/LIGHTNING events; agreement metrics
8 (stretch)	MCP client helper & mock server	optional vertical context fetch


⸻

10 · Risks & mitigations

Risk	Impact	Mitigation
HTTP latency adds wall-time	+50–80 ms per agent	keep max_concurrent_workers 6-10, run in same VPC
Agent crash stalls verdict	dimension “pending” forever	Root sets agent timeout; if expired → fallback to monolith
JSON parse fails (as seen before)	0-score dim	stricter schema validation inside each agent before posting result
Websocket event ordering	UI jitter	attach sequence_id field; client sorts


⸻

11 · Conclusion

We retain the proven prompt + scoring logic while unlocking:
	•	Elastic parallelism (agents autoscale)
	•	Per-dimension model tuning (cheap vs premium)
	•	Protocol future-proofing (A2A now, MCP next)
	•	Cleaner UX — first insights stream the moment a single agent finishes.

This design vaults Steer QA from “clever linter” to a production micro-mesh that any agentic platform can plug into—ready for enterprise scale.