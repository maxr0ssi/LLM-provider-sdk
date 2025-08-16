# Repository Cleanup & Audit Report (Pre-Release)

This report lists redundancies, inefficiencies, drift, and recommended edits before publishing the package. It reflects the Phase 7 migrations (OpenAI Agents SDK) and the pricing refactor to ModelConfig.

## Executive summary

- Agents runtime: OpenAI Agents SDK only, capability-driven params, streaming via bridge, light metrics.
- Pricing: Move to `ModelConfig` for all models; remove constant-based fallbacks.
- Cleanup focus: consolidation, doc consistency, remove legacy fallbacks/duplication.

## High-priority items (P0)

1) Single-source pricing (configs only)
- Files: `steer_llm_sdk/core/routing/selector.py`, `steer_llm_sdk/core/routing/router.py`
- Problem: Selector/router still import `config/constants.py` as fallback for some models.
- Action:
  - Ensure every supported model has `input_cost_per_1k_tokens`, `output_cost_per_1k_tokens`, optional `cached_input_cost_per_1k_tokens`.
  - Remove constant-based fallbacks in selector/router.
  - Keep `constants.py` only for metadata (LAST_VERIFIED, URLs) or delete if unused.

2) Eliminate mapping duplication in agents integration
- Files: `steer_llm_sdk/integrations/agents/mapping.py` vs core normalization/policy
- Problem: Duplicated helpers (`prepare_schema_for_responses_api`, `map_token_limit_param`).
- Action: Remove duplicates; import core policies instead.

3) Normalize streaming JSON/event handling
- Files: `streaming/adapter.py`, `integrations/agents/streaming.py`, `api/client.py`
- Problem: Risk of multiple layers parsing JSON/aggregating usage.
- Action: Make `StreamAdapter`/`AgentStreamingBridge` the only owners of JSON parsing and usage aggregation; client should not re-parse.

4) Docs: “No fallback” for agent runtime
- Files: `docs/integrations/openai-agents/*`, guides
- Action: Verify agent docs state “no fallback”; remove residual fallback mentions in agent context.

## Important items (P1)

5) Centralize cost computation
- Files: adapters/router/selector
- Action: Adapters call only `calculate_exact_cost` (+ optional `calculate_cache_savings`). No adapter-local cost math.

6) Error class duplication
- Files: `integrations/agents/errors.py`, `reliability/errors.py`
- Action: Use base `ProviderError`; keep only mappers returning base errors with metadata.

7) Large-file hotspots
- Files: `providers/openai/adapter.py`
- Action: Keep adapter thin; delegate to `payloads.py`, `parsers.py`, `streaming.py`.

8) StreamingOptions vs reliability knobs
- Files: `models/streaming.py`, `core/routing/router.py`
- Action: Ensure single per-call source (`StreamingOptions`); router respects it; remove duplicates.

9) Tool schema handling location
- Files: `integrations/agents/openai/tools.py`
- Action: Keep all tool-to-SDK conversion here; remove alternates.

## Medium items (P2)

10) EventManager usage consistency
- Action: Prefer EventManager methods or bridge; avoid raw event object construction outside owners.

11) Packaging footprint
- Files: `MANIFEST.in`
- Action: Consider excluding tests/examples from sdist if shipping to PyPI.

12) README/API reference drift
- Action: Ensure API reference/examples reflect split streaming API only.

## Completed in this phase

- Agents SDK adapter uses `AgentStreamingBridge` with `_last_bridge` aggregation and TTFT.
- Docs added for OpenAI Agents SDK; agent fallback removed; README updated for split streaming API.
- Packaging extras for `openai-agents` in pyproject/setup.
- Pricing plan: migrate to `ModelConfig` and remove constant fallbacks.

## Suggested ordering

1) Pricing consolidation — P0
2) Remove mapping duplication — P0
3) JSON/event ownership verification — P0
4) Use base `ProviderError` — P1
5) Adapter size trims — P1
6) StreamingOptions dedupe/router respect — P1
7) EventManager consistency — P2
8) Packaging footprint — P2

## Concrete edits checklist

- selector/router pricing
  - [ ] `selector.calculate_exact_cost`: only `ModelConfig` pricing; delete constants fallbacks
  - [ ] `selector.calculate_cache_savings`: only `ModelConfig.cached_input_cost_per_1k_tokens`
  - [ ] `router.generate`: use selector; remove model-specific constants branches

- agents mapping
  - [ ] Remove duplicated schema/token mapping; import core policies

- streaming ownership
  - [ ] Ensure only bridge/adapter parse JSON and aggregate usage

- errors
  - [ ] Return base `ProviderError` from mappers; remove custom subclass

- adapters
  - [ ] OpenAI adapter delegates payload/parse/stream to helper modules

- options
  - [ ] Remove duplicated timeout/retry knobs; pass `StreamingOptions` through router

- docs
  - [ ] No agent fallback wording; API ref matches split streaming API

- packaging
  - [ ] Decide whether to exclude tests/examples from sdist

## References

- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/
- Pricing sources: official pricing pages (recorded in metadata)
