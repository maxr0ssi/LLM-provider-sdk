# OpenAI Agents SDK Integration — Overview

This documentation defines the target for Phase 7: a first-class integration of the OpenAI Agents SDK across our SDK, with **no fallback paths**. The OpenAI Agents SDK is a required dependency for agent runtime functionality.

- Required package: `pip install steer-llm-sdk[openai-agents]`
- Reference docs: [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)

> Provider-agnostic positioning: the SDK remains provider-agnostic. The agent runtime is pinned to `openai_agents` with no fallback; additional runtimes remain pluggable for future releases.

## Intent and scope

- Provide a dedicated Agents runtime that uses the OpenAI Agents SDK primitives (Agents, Runner, Tools, Sessions, Guardrails, Streaming, Tracing).
- Preserve our normalized outputs (content, usage, cost, provider metadata) and standard streaming events.
- Keep reliability and metrics light pre-production; enable basic request timing and optional TTFT, but avoid heavy instrumentation initially.

## What we have vs what we want

- What we had: A chat-completions based “agent-like” adapter. This is deprecated for Phase 7 goals.
- What we want: A true Agents SDK runtime with:
  - Native agent loop and tool invocation
  - Optional strict JSON schema enforcement for structured outputs
  - Streaming event bridging to our callbacks
  - Minimal, opt-in observability

## High-level constraints

- **No fallback**: Agent runs must use the OpenAI Agents SDK. There is no Chat Completions API fallback.
- Clean architecture: Agents runtime lives under `integrations/agents/openai/` and does not leak provider-specific behavior into core layers.
- Capability-driven behavior: token field mapping, temperature policy, and seed forwarding remain policy-based (not model-name switches).

## Supported features (initial)

- Agents + Runner (sync/async, streaming)
- Tools (Python functions with JSON-schema parameters)
- Guardrails for structured outputs (strict mode where supported)
- Minimal metrics (duration, optional TTFT); optional request/trace IDs

## Out of scope (initial)

- Complex multi-agent handoffs or external orchestration
- Deep tracing integration (beyond basic IDs)
- Heavy, production-grade metrics by default

## Determinism and Idempotency Semantics

- Determinism: when a `seed` is provided and the model supports it, the runtime forwards it; otherwise it is a no-op with a warning.
- Idempotency: same `idempotency_key` + same payload → return stored result; with different payload → conflict (HTTP 409 equivalent) with structured error.

## Streaming Event Schema (minimal)

- `on_start`: `{ provider, model, request_id?, metadata? }`
- `on_delta`: `{ delta: str | dict, is_json?: bool, chunk_index }`
- `on_usage`: `{ usage: dict, is_estimated: bool, confidence?: float }`
- `on_complete`: `{ total_chunks, duration_ms, final_usage?, metadata? }`
- `on_error`: `{ error: { code, message, retriable? } }`

A redaction hook can be installed to remove PII/secrets before events leave the process.

## Diagrams and flows

See `diagrams/flows.md` for ASCII architecture and sequence flows.

## Preflight Checklist

Before using the OpenAI Agents runtime, ensure the following:

1. **Install the SDK with Agents support**: 
   ```bash
   pip install steer-llm-sdk[openai-agents]
   ```

2. **Configure API Key**: 
   - Set `OPENAI_API_KEY` environment variable
   - The adapter will validate this on initialization

3. **Validate Tool Schemas** (if using tools):
   - Ensure all tool parameters follow JSON Schema format
   - Tool handlers must be callable (sync or async functions)
   - Review tool compatibility warnings during preparation

4. **JSON Schema Requirements** (if using structured outputs):
   - Schema must be valid JSON Schema draft 7
   - When using strict mode, ensure schema has `additionalProperties: false`
   - Test schema validation with sample outputs

5. **Rate Limit Considerations**:
   - Agent runs may involve multiple API calls (tool executions)
   - Monitor usage to avoid rate limit errors
   - Consider implementing retry logic at the application level

6. **Streaming Configuration**:
   - For streaming runs, provide EventManager callbacks
   - Events are normalized through AgentStreamingBridge
   - Final content/usage available via bridge after stream completes

See `implementation.md` for detailed usage patterns and examples.


