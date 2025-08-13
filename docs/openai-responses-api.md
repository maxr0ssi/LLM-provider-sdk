## OpenAI Responses API — SDK Usage Guide

### What it is
The Responses API is OpenAI’s unified endpoint for text and multimodal generation that consolidates capabilities (structured output, tool calls, streaming, and metadata) behind a single request/response shape.

- Official docs: [Responses API reference](https://platform.openai.com/docs/api-reference/responses)
- Overview: [New tools and features in the Responses API](https://openai.com/index/new-tools-and-features-in-the-responses-api/)
- Model notes:
  - GPT‑4.1 mini: [Model overview](https://openai.com/index/gpt-4-1/)
  - GPT‑5 mini: [Introducing GPT‑5 for developers](https://openai.com/index/introducing-gpt-5-for-developers/)

### Why we use it in the SDK
- Structured outputs via `response_format: { type: "json_schema", json_schema: {...} }` reduce parse failures.
- Deterministic runs via `seed` (when supported) and conservative parameters for CI stability.
- Streaming with usage enables low-latency UX and accurate cost tracking.
- Capability-driven: the SDK checks provider/model capabilities to choose the safest path.

### Core request shape (conceptual)
The SDK maps `AgentDefinition` to a Responses API payload when supported by the selected model. Otherwise it falls back to the provider’s chat/messages API and performs post‑hoc validation.

```json
{
  "model": "gpt-5-mini",
  "input": [
    { "role": "system", "content": "You are a structured extractor." },
    { "role": "user",   "content": "Extract key facts from: ..." }
  ],
  "text": {
    "format": {
      "type": "json_schema",
      "name": "result",
      "schema": {
        "type": "object",
        "properties": {
          "summary": { "type": "string" },
          "key_points": { "type": "array", "items": { "type": "string" } }
        },
        "required": ["summary", "key_points"],
        "additionalProperties": false
      }
    }
  },
  "top_p": 1.0,
  "max_output_tokens": 256,
  "seed": 42
}
```

Notes:
- For JSON schema mode, use `text.format` with `type: "json_schema"`, a `name`, and a `schema`. The schema must include `additionalProperties: false` at the root.
- For `gpt-5-mini`, `temperature` is not supported in Responses API; the SDK omits it automatically.
- For streaming, the SDK uses SSE and emits normalized deltas; in-stream usage may not be available and is emitted on completion when supported.
- Optional knobs:
  - `strict`: set `text.format.strict=true` to enforce stricter schema adherence.
  - `responses_use_instructions`: map the first `system` message to the `instructions` field (and remove it from `input`).
  - `reasoning`: pass through Responses reasoning config when supported (e.g., effort levels).
  - `metadata`: pass through request metadata (e.g., trace_id, run_id).

### Streaming
- The Responses API supports SSE streaming. The SDK provides a normalized streaming adapter that emits generic callbacks:
  - `on_start` → first byte/metadata
  - `on_delta` → text or JSON deltas
  - `on_usage` → token usage (when provider supports in-stream usage)
  - `on_complete` → final aggregated result
  - `on_error` → typed error

When usage is not available during stream, the SDK emits usage on completion.

### Structured output (JSON schema)
- If the chosen model supports native schema (e.g., GPT‑4.1 mini, GPT‑5 mini), the SDK sends `response_format: { type: "json_schema", json_schema: {...} }` and returns validated JSON.
- If not supported natively, the SDK performs best‑effort post‑validation: parse text → JSON → validate → raise `SchemaError` on failure. Optional local tools (e.g., `json_repair`) may be applied if enabled.

### Tool calling
- The Responses API supports function tools. The SDK, by design, keeps tools local and deterministic for portability and predictable costs.
- For agent runs that include tools, the SDK validates tool parameters against their JSON schema and executes handlers locally, then feeds the results back into the LLM turn if needed.
- Mapping to provider tool calls can be added later behind capability flags if required.

### Determinism and idempotency
- Deterministic mode: the SDK clamps parameters (e.g., `temperature=0`) and propagates `seed` where supported.
- Idempotency: callers may supply an `idempotency_key`. The SDK provides an in‑memory `IdempotencyManager` for request dedup during retries.

### Model support (focused)
- GPT‑4.1 mini
  - Supported by Responses API.
  - Good fit for deterministic structured extraction with low cost.
  - SDK capability flags: `supports_json_schema=True`, `supports_streaming=True`, `supports_seed=True` (best‑effort).

- GPT‑5 mini
  - Supported by Responses API.
  - Preferred for Intent/Lightning style structured outputs where available.
  - SDK capability flags: `supports_json_schema=True`, `supports_streaming=True`, `supports_seed=True`.
  - Nuance: do not send `temperature` in Responses API calls (unsupported).

### Using it for agents (SDK flow)
1) Define an `AgentDefinition` with `system`, `user_template`, optional `json_schema`, and `model` (e.g., `gpt-5-mini` or `gpt-4.1-mini`).
2) Call `AgentRunner.run(definition, variables, options)`.
3) The runner:
   - Resolves provider capabilities for the model
   - Applies deterministic policy and budgets
   - If `json_schema` provided and supported → uses Responses API; else falls back to messages API
   - Streams via normalized callbacks and returns a validated `AgentResult`

### Example (conceptual SDK usage)
```python
agent = AgentDefinition(
    system="You extract structured data.",
    user_template="Extract key facts from: {text}",
    json_schema={"type":"object","properties":{"facts":{"type":"array","items":{"type":"string"}}},"required":["facts"]},
    model="gpt-5-mini",
    parameters={"temperature": 0.0}
)

result = await AgentRunner().run(
    agent,
    variables={"text": source_text},
    options={"deterministic": True, "idempotency_key": run_id}
)
print(result.content)  # Validated JSON
```

### References
- Responses API: [platform.openai.com/docs/api-reference/responses](https://platform.openai.com/docs/api-reference/responses)
- Responses API updates: [openai.com/index/new-tools-and-features-in-the-responses-api](https://openai.com/index/new-tools-and-features-in-the-responses-api/)
- GPT‑4.1 overview: [openai.com/index/gpt-4-1](https://openai.com/index/gpt-4-1/)
- GPT‑5 developers: [openai.com/index/introducing-gpt-5-for-developers](https://openai.com/index/introducing-gpt-5-for-developers/)


