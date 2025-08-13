## OpenAI Agents (Guide + SDK pointers)

### What this is
- Quick notes on OpenAI’s Agents guidance and the OpenAI Agents SDK, with links and how this maps to our SDK.

### References
- Agents guide (OpenAI): https://platform.openai.com/docs/guides/agents
- OpenAI Agents SDK docs: https://openai.github.io/openai-agents-python/
- OpenAI Agents SDK repo: https://github.com/openai/openai-agents-python

### Concepts (from OpenAI Agents)
- Agent = LLM with instructions and tools; may loop until final output.
- Tools = callable functions (JSON‑schema parameters), can be local or remote.
- Handoffs = delegate to other agents.
- Guardrails = validate inputs/outputs, can short‑circuit agent loop.
- Sessions = conversation state; tracing = built‑in telemetry.

### OpenAI Agents SDK highlights
- Minimal primitives: Agents, Tools, Handoffs, Guardrails, Sessions, Tracing.
- Built‑in agent loop (handles tool calls and iteration until completion).
- Pydantic‑powered schemas for tools and structured outputs.
- Streaming and REPL utilities for development.
- MCP support and orchestration patterns (multi‑agent).

### Mapping to our SDK
- Our SDK focuses on:
  - Provider‑agnostic plumbing (OpenAI Responses API preferred; Anthropic/xAI supported).
  - AgentDefinition + AgentRunner (opt‑in) with JSON schema outputs, deterministic mode, idempotency, local deterministic tools, normalized streaming.
  - Clear separation from OA/orchestrator logic; no built‑in multi‑agent loop or handoffs.

- Interop expectations:
  - Tools: both systems use JSON‑schema for parameters and deterministic handlers → easy to mirror functions.
  - Structured output: Responses API `text.format = { type: "json_schema", name, schema }` aligns with Agents SDK “output_type”.
  - Streaming: our normalized callbacks map cleanly to Agents SDK streaming events.
  - Sessions/Tracing: we intentionally keep these out of core; can be added via hooks to match Agents SDK capabilities if needed.

### Practical notes (OpenAI Responses API)
- Use Responses API for schema‑backed agents (e.g., `gpt‑4.1‑mini`, `gpt‑5‑mini`).
- JSON schema must include `additionalProperties: false` at the root.
- For `gpt‑5‑mini`, omit `temperature` in Responses API requests.

### When to consider OpenAI Agents SDK directly
- You want the built‑in loop (tools + iteration until a typed final output) and sessions/tracing out of the box.
- You’re building an OpenAI‑only stack and prefer their opinionated agent runtime.

### When to prefer our SDK
- Multi‑provider targets, clean separation of concerns, and minimal surface for orchestration.
- Determinism/idempotency and cost/usage normalization across providers.


