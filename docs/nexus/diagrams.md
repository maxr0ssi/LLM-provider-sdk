### Topology (Root orchestration with Stage/Dimension sub-agents)
```
                 ┌───────────────────────────┐
                 │       Root Orchestrator   │
                 │  (Multistage + K×D logic) │
                 └───────────┬───────────────┘
       Local (in-proc)       │        A2A (HTTP+JWT)
   ┌─────────────────────┐   │
   │  Static Checks      │   │   ┌──────────────────────┐
   │  (gating, optional) │   │   │   Intent-Agent       │
   └─────────────────────┘   │   └──────────────────────┘
                             │             │
                             │             ▼
                             │   ┌──────────────────────┐
                             │   │  Lightning-Agent     │
                             │   └──────────────────────┘
                             │
     ┌───────────────────────┼───────────────────────────────────────────────┐
     ▼                       ▼                      ▼                        ▼
┌──────────────┐       ┌──────────────┐      ┌──────────────┐          ┌──────────────┐
│ Clarity-Agent│  …    │ Structure-Ag │ …    │ Feasibility  │   …      │ Referee-Agent│
│ (replica svc)│       │ (replica svc)│      │  -Agent      │          │ (aggregation)│
└──────────────┘       └──────────────┘      └──────────────┘          └──────────────┘

- Root is the single brain (control-plane): stages, scheduling, early-exit, K replicas.
- Static runs locally (Python checks) before agents. Intent-Agent produces the ScoringContract.
- Agents are stateless (data-plane): run replicas and return verdict JSON.
- No agent-to-agent side channels; all coordination is Root-routed.
```

### End-to-end macro flow (authoritative order)
```
Client/CLI/TUI
   │  /evaluate(prompt)
   ▼
Root Orchestrator
   │─► Static checks (local; gating)
   │    └─ emit STATIC_CHECK_COMPLETE; stop if critical gate fires
   │─► Intent-Agent (A2A)
   │    └─ emit INTENT_EXTRACTION_COMPLETE; build ScoringContract
   │─► Lightning-Agent (A2A)
   │    └─ emit LIGHTNING_COMPLETE; caps recorded
   │─► Parallel K×D fan-out (TaskOffer replicas to Dimension Agents)
   │◄─ TaskResult (ReplicaVerdict) × replicas
   │   Early-exit after K=2? If yes → skip K=3
   │─► Referee Agent (or local referee)
   │◄─ Referee verdict / fallback
   │→ StreamEvents to TUI: STATIC_CHECK_COMPLETE, INTENT_EXTRACTION_COMPLETE,
   │                       LIGHTNING_COMPLETE, REPLICA_COMPLETE,
   │                       DIMENSION_COMPLETE, FINAL
   ▼
Client/CLI/TUI
```

### Replica-level flow (one “sub-agent” = one replica)
```
Root:
- compute run_id, temperature, seed (same mapping as today)
- POST /task_offer {
    task_id, dimension, run_id, temp, seed,
    prompt, scoring_contract, dimension_cap,
    trace_id, idempotency_key, version
  }

Dimension-Agent:
- validate offer; run existing dimension worker; produce ReplicaVerdict
- POST /task_result { task_id, verdict:{dimension, run_id, score, annotations[], confidence, tokens_used, duration_ms, temp, seed}, elapsed_ms, model }

Root:
- emit REPLICA_COMPLETE (StreamEvent)
- update K-count, early-exit check; if needed, queue K=3 (fast lane)
- on completion, aggregate and emit DIMENSION_COMPLETE
```

### Failure, idempotency, fallback (Root policy)
```
For each replica:
- Timeout T: if no /task_result by T → cancel-internal, fallback to local execution
- Retry with same idempotency_key on 5xx (agent must be idempotent)
- On error in verdict: mark replica failed; use baseline or fallback policy in aggregation
- Root records task lifecycle; TUI still streams timely dimension events
```

### Scheduling and fairness (preserve today’s behavior)
```
- K×D planner across dimensions
- Early-exit after K=2 if std < threshold
- K=3 created only if needed; goes to fast-lane
- Per-agent concurrency caps (capacity) to avoid overload
- Backpressure: queue depth signals autoscale
```

### Security and observability (minimal)
```
- JWT (iss=root, aud=<agent>) per offer; allow-list agent URLs
- Envelope fields: version, message_type, task_id, trace_id, idempotency_key, issued_at/ttl
- Metrics at Root/Agents: offers_total, results_total, timeouts_total, latency p50/p95
- Health/Ready endpoints on Root and Agents
```

### Deployment (incremental hybrid)
```
+-------------------+        +------------------+         +------------------+
| Root-Orchestrator |  ----> | Clarity-Agent    |   ...   | Referee-Agent    |
| (k8s/Run)         |        | (k8s/Run)        |         | (k8s/Run)        |
+-------------------+        +------------------+         +------------------+

Rollout:
- Start with 1–2 dimensions remote; others local (mode=hybrid)
- Feature flag: evaluation.mode = local | a2a | hybrid
- Canary traffic; expand as metrics stay green
```

If you want these saved, I propose:
- `docs/Todo/Nexus/DIAGRAMS.md` with the sections above.