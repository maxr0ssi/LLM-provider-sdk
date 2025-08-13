## Refactoring Plan – Layered Modular SDK

### Phase 0 – Baseline validation
- Confirm all smoke tests pass (Responses API, determinism, retry, back‑compat).
- Freeze public API surface snapshot.

### Phase 1 – Contracts & Normalization
- Formalize `GenerationParams` fields (responses flags, seed) in models and docs.
- Implement `usage_normalizer` to enforce usage dict shape across providers.
- Standardize streaming `on_usage` emission (always at end when not in‑stream).

### Phase 2 – Capability registry hardening
- Audit model entries for OpenAI/Anthropic/xAI; complete flags and token‑field mappings.
- Make router param naming decisions solely from capabilities (e.g., `max_output_tokens`).

### Phase 3 – Provider adapters clean‑split
- Ensure provider modules expose only the adapter interface; move any stray logic into decision/normalizer layers.
- Replace any print calls with structured logging (already mostly done).

### Phase 4 – Streaming/event consistency
- Ensure all adapters stream deltas consistently; unify JSON vs text deltas via `StreamAdapter`.
- Emit usage once on completion when not available in‑stream.

### Phase 5 – Errors, retries, idempotency
- Confirm providers raise typed `ProviderError`; wrap transport errors consistently.
- Verify `RetryManager` paths and idempotency checks in AgentRunner for both streaming and non‑streaming.

### Phase 6 – Metrics
- Confirm `AgentMetrics` fields are populated uniformly; add simple example sink in docs.

### Phase 7 – Documentation & Examples
- Update user guides and architecture docs to reflect final structure.
- Add example snippets for: new provider, new model, local adapter.

### Phase 8 – Optional adapters (outside core)
- Provide reference adapter example for OpenAI Agents SDK in a separate repo or `integrations/` folder.

### Acceptance
- New provider/model can be added by implementing adapter + capability entries + two smokes (generate/stream).


