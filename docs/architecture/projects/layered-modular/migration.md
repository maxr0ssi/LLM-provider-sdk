## Migration – Layered Modular SDK

### Backward compatibility
- `SteerLLMClient` public methods remain, but legacy shim modules have been removed.
- Agent APIs (definitions/runner) remain the same; only internals are organized by layers.

### Changes to note
- Usage dict: now guaranteed keys `{prompt_tokens, completion_tokens, total_tokens, cache_info}` across providers.
- OpenAI structured outputs: Responses API path used automatically when `json_schema` is present and supported; `additionalProperties=false` required at root; temperature omitted for GPT‑5 mini.
- Determinism: clamped parameters by default when enabled; `seed` forwarded when supported.

### Removed shims (Phase 0.5 complete)
- Removed compatibility modules and re-exports:
  - `steer_llm_sdk/main.py` (use `steer_llm_sdk.api.client`)
  - `steer_llm_sdk/LLMConstants.py` (use `steer_llm_sdk.config.constants`)
  - `steer_llm_sdk/llm/__init__.py` (use `steer_llm_sdk.core.*`)
  - `steer_llm_sdk/llm/providers/{__init__.py, openai.py, anthropic.py, xai.py}` (use `steer_llm_sdk.providers.<provider>.adapter`)

### New import paths
- Client: `from steer_llm_sdk.api.client import SteerLLMClient`
- Router/core: `from steer_llm_sdk.core.routing import LLMRouter, get_config, normalize_params`
- Capabilities: `from steer_llm_sdk.core.capabilities import get_model_capabilities, ProviderCapabilities`
- Providers: `from steer_llm_sdk.providers.openai.adapter import OpenAIProvider`

### Action items for consumers
- If you rely on provider‑specific usage fields, switch to the normalized usage dict.
- For strict JSON outputs, add `additionalProperties: false` to schema root.
- To leverage provider‑native agent systems (OpenAI Agents SDK), follow the optional integration plan outside core.

### Versioning
- Changelog notes under 0.3.0 (in progress) reflect removal of shims and directory restructuring completion.


