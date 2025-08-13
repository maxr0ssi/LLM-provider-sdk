# A2A Protocol v1 (SteerQA V2)

Scope: Root ⇄ Agent HTTP contracts (evaluation quality only). Authentication, quotas, and persistence are out of scope.

## Envelope (all requests/responses)

Required fields:
- `version` (string) — protocol version, e.g., `"1.0"`
- `message_type` (string) — `task_offer`, `task_result`, `error`
- `task_id` (string)
- `trace_id` (string)
- `issued_at` (ISO8601)
- `ttl` (ms)
- `idempotency_key` (string)
- `agent_version` (string)

## Offers

### Intent Offer (Root → Intent-Agent)
```json
{
  "version": "1.0",
  "message_type": "task_offer",
  "task_id": "intent-7421",
  "trace_id": "...",
  "issued_at": "2025-08-12T12:00:00Z",
  "ttl": 3000,
  "idempotency_key": "...",
  "agent_version": "intent@0.1.3",
  "prompt": "...",
  "hints": {"static_findings": []},
  "policy": {"max_latency_ms": 2000}
}
```

### Dimension Offer (Root → Dimension-Agent)
```json
{
  "version": "1.0",
  "message_type": "task_offer",
  "task_id": "clarity-9843",
  "trace_id": "...",
  "issued_at": "2025-08-12T12:00:01Z",
  "ttl": 5000,
  "idempotency_key": "...",
  "agent_version": "clarity@0.1.0",
  "prompt": "...",
  "scoring_contract": {"schema_version": "1.0"},
  "dimension": "clarity",
  "dimension_cap": 75,
  "k_replicas": 3,
  "run_id": "r1",
  "seed": 1
}
```

## Results

### Intent Result (Agent → Root)
```json
{
  "version": "1.0",
  "message_type": "task_result",
  "task_id": "intent-7421",
  "trace_id": "...",
  "agent_version": "intent@0.1.3",
  "intent_packet": {"objective": "...", "requirements": [], "constraints": []},
  "scoring_contract": {"schema_version": "1.0"},
  "confidence": 0.86,
  "elapsed_ms": 640,
  "model": "gpt-4.1-mini"
}
```

### Replica Result (Agent → Root)
```json
{
  "version": "1.0",
  "message_type": "task_result",
  "task_id": "clarity-9843",
  "trace_id": "...",
  "agent_version": "clarity@0.1.0",
  "verdict": {"dimension": "clarity", "run_id": "r1", "score": 58, "annotations": [], "confidence": 0.72},
  "elapsed_ms": 812,
  "model": "gpt-4.1-mini"
}
```

## Errors

Error response schema:
```json
{
  "version": "1.0",
  "message_type": "error",
  "task_id": "clarity-9843",
  "trace_id": "...",
  "code": "SCHEMA_VALIDATION_FAILED",
  "message": "...",
  "retryable": true
}
```

## Retries and Idempotency
- Root retries `5xx` with same `idempotency_key`.
- Agents must ensure idempotent `task_result` for the same key.

## Ordering and Streaming
- Root assigns `sequence_id` and `dimension_seq` for emitted events.
- Core events: `STATIC_CHECK_COMPLETE`, `INTENT_EXTRACTION_COMPLETE`, `LIGHTNING_COMPLETE`, `REPLICA_COMPLETE`, `DIMENSION_COMPLETE`, `FINAL`.

## Partial Results and Hints (OA drip-feed)

To enable OA-mediated drip-feed without agent side-channels, agents MAY return interim payloads before the final verdict.

- Transport: keep `message_type="task_result"` and include a `"status": "partial" | "final"` discriminator.
- Partial payloads MUST be self-contained and non-derivative (no references to other agents’ outputs except OA-provided snapshots included in the offer).

### Dimension Early Result (partial)
```json
{
  "version": "1.0",
  "message_type": "task_result",
  "status": "partial",
  "task_id": "clarity-9843",
  "trace_id": "...",
  "agent_version": "clarity@0.1.0",
  "early_result": {
    "dimension": "clarity",
    "run_id": "r1",
    "score_stub": 55,
    "top_issue_title": "Open-Ended Role Scope"
  },
  "elapsed_ms": 420
}
```

### Referee Arbitration Hint (partial)
```json
{
  "version": "1.0",
  "message_type": "task_result",
  "status": "partial",
  "task_id": "ref-7721",
  "trace_id": "...",
  "agent_version": "referee@0.1.0",
  "arbitration_hint": {
    "conflict_risk": 0.72,
    "suggest_third_replica": ["clarity"],
    "cap_violation_risk": {"structure": true}
  }
}
```

### Final Result (unchanged)
Final results omit `status` or set `status="final"` and include the standard `verdict` object.


