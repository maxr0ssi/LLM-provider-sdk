# SDK – Nexus MVP Progress Tracker

Status legend: [x] done, [>] in progress, [ ] todo

## Core
- [x] Agent primitives (AgentDefinition, AgentOptions, AgentResult)
- [x] AgentRunner with streaming callbacks (EventManager) and StreamAdapter (text)
- [x] JSON schema validator (post‑hoc)
- [x] Determinism helper (central clamp + seed best‑effort)
- [x] IdempotencyManager (TTL + LRU) and integration in runner
- [x] Capability registry scaffold (per‑model flags)
- [x] OpenAI Responses API mapping (text.format json_schema, add additionalProperties=false)
- [x] GPT‑5 mini nuance: omit temperature in Responses calls
- [x] Responses streaming branch with safe fallback; Chat streaming intact

## Providers & Capabilities
- [x] Finalize capability registry per model (json_schema, seed, max_output_tokens, temperature support, fixed_temperature)
- [x] Remove residual model‑name heuristics in providers; use capabilities exclusively (OpenAI)
 - [x] Normalize usage dict across providers (prompt_tokens, completion_tokens, total_tokens, cache_info)
- [x] Logging hygiene in all providers (no prints; debug via logger)

## Determinism, Errors, Retries
- [x] Central determinism clamp helper
- [x] Delete ad‑hoc per‑provider clamps in favor of central policy (OpenAI)
- [x] Typed errors end‑to‑end (ProviderError, SchemaError, TimeoutError, BudgetExceededError)
- [x] Minimal RetryManager for retryable classes (non‑stream path wired)

## Streaming
- [x] Basic StreamAdapter (text deltas)
- [x] StreamAdapter: support JSON deltas
- [x] Standardize on_usage emission (once at end when in‑stream usage not available)

## Tools (local deterministic)
- [x] Tools scaffold (Tool + ToolExecutor with JSON‑schema param validation)
- [x] Built‑ins: format_validator, extract_json, json_repair (feature flag optional)
- [x] Helper to derive JSON schema from Python callables (pydantic‑style)

## Metrics & Hooks
- [x] Pluggable MetricsSink (OTel optional) and emission of request_id, model, latency_ms, tokens, cache_savings, retries, error_class, tools_used (hooked in runner)
- [x] Docs: how to plug custom sink
 
## Docs & Examples
- [x] Architecture overview (docs/sdk-architecture.md)
- [x] Responses API guide (docs/openai-responses-api.md)
- [x] Implementation plan updates (docs/nexus/IMPLEMENTATION_PLAN.md)
- [x] Agents vs OpenAI Agents SDK notes (docs/useful/agents-open-ai.md)
 - [ ] Examples: strict schema + gpt‑5‑mini; instructions vs system; streaming JSON deltas
- [x] Document new parameters: strict, responses_use_instructions, reasoning, metadata

## Tests & CI
- [x] Smoke tests for Responses API (gpt‑4.1‑mini, gpt‑5‑mini)
- [x] Expand smoke: strict=true; instructions mapping on/off; determinism assertions; transient error → retry path (strict/instructions added)
- [x] Lint/type checks + file LOC guard (< 400 LOC/file)
 - [x] Backward‑compat tests for legacy generate/stream

## Release Hygiene
- [ ] Version bump and CHANGELOG
- [ ] Migration notes (Responses API adoption, strict schema, instructions mapping)

## Notes / Decisions
- Use Responses API for structured outputs on supported models; enforce additionalProperties=false at schema root; omit temperature on GPT‑5 mini.
- Keep SDK provider‑agnostic; no OA logic; agents opt‑in.
