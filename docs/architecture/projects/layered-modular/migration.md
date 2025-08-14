## Migration – Layered Modular SDK

### Backward compatibility
- `SteerLLMClient` methods remain unchanged.
- Agent APIs (definitions/runner) remain the same; only internals are organized by layers.

### Changes to note
- Usage dict: now guaranteed keys `{prompt_tokens, completion_tokens, total_tokens, cache_info}` across providers.
- OpenAI structured outputs: Responses API path used automatically when `json_schema` is present and supported; `additionalProperties=false` required at root; temperature omitted for GPT‑5 mini.
- Determinism: clamped parameters by default when enabled; `seed` forwarded when supported.

### Action items for consumers
- If you rely on provider‑specific usage fields, switch to the normalized usage dict.
- For strict JSON outputs, add `additionalProperties: false` to schema root.
- To leverage provider‑native agent systems (OpenAI Agents SDK), follow the optional integration plan outside core.


