# Intent Contract (v1)

Purpose: Standardize evaluation inputs across Lightning and Dimension Agents by extracting intent and producing a ScoringContract.

## IntentPacket
```json
{
  "objective": "Write a Python tutorial...",
  "requirements": [
    {"id": "REQ-1", "text": "Include 3 exercises", "must": true},
    {"id": "REQ-2", "text": "Use real-world analogies", "must": false}
  ],
  "constraints": [
    {"id": "CON-1", "text": "No external dependencies"}
  ],
  "focus_aspects": ["role", "audience", "scope", "deliverables"],
  "notes": []
}
```

## ScoringContract
```json
{
  "schema_version": "1.0",
  "objective": "...",
  "requirements": [{"id":"REQ-1","text":"...","must":true}],
  "constraints": [{"id":"CON-1","text":"..."}],
  "dimension_weights": {"clarity":1.2, "structure":1.0, "feasibility":1.1, "safety":1.0},
  "dimension_thresholds": {"clarity":75, "structure":70, "feasibility":90, "safety":80},
  "focus_aspects": ["role","audience"],
  "caps": {"max_score_by_gate": {"world_class_gate":85}},
  "examples": {"world_class":"...", "non_examples":["..."]},
  "provenance": {"intent_agent":"v0.1.3", "prompt_hash":"...", "trace_id":"..."}
}
```

## Requirements
- Deterministic option (seed) for reproducibility
- Strict JSON schema validation before return
- Backward compatible evolution via schema_version (additive fields only)

## Consumption
- Lightning: reads caps and applies early classification
- Dimension Agents: use dimension_weights/thresholds and requirements
- Referee: checks cross-dimension consistency against the contract
