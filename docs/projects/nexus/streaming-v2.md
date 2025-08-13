# Streaming v2 (Domain Events)

Purpose: Standardize append-only streaming events across stages and dimensions with ordering.

## Event Types
- STATIC_CHECK_COMPLETE
- INTENT_EXTRACTION_COMPLETE
- LIGHTNING_COMPLETE
- REPLICA_COMPLETE
- DIMENSION_COMPLETE
- FINAL
- Optional: TOKEN_UPDATE

## Ordering
- Root assigns sequence_id (global) and dimension_seq (per dimension)
- Clients render append-only; status lines may overwrite locally

## Payload Hints
- STATIC_CHECK_COMPLETE: { summary, gating_decision }
- INTENT_EXTRACTION_COMPLETE: { key_requirements, thresholds }
- LIGHTNING_COMPLETE: { caps_applied }
- REPLICA_COMPLETE: { dimension, replica_id, score, confidence }
- DIMENSION_COMPLETE: { dimension, score, agreement, annotations_count }
- FINAL: { aggregate_score, passed, dimension_scores }

## Drip-Feed Extensions (OA-mediated)
- DIMENSION_EARLY_RESULT: { dimension, replica_id, score_stub, top_issue_title }
- ARBITRATION_HINT: { conflict_risk, suggest_third_replica[], cap_violation_risk }

### Throttling & Ordering
- OA may buffer partials and emit at most one EARLY_RESULT per dimension at a time.
- Maintain monotonic sequence_id across partial and final events.
