## Phase 7 – Agents Integrations Runtime (Technical Design)

### 1) Core Interface and Models

#### 1.1 `AgentRuntimeAdapter` (ABC)
```python
class AgentRuntimeAdapter(Protocol):
    def supports_schema(self) -> bool: ...
    def supports_tools(self) -> bool: ...

    async def prepare(self, definition: AgentDefinition, options: AgentRunOptions) -> PreparedRun: ...
    async def run(self, prepared: PreparedRun, variables: dict) -> AgentRunResult: ...
    async def run_stream(self, prepared: PreparedRun, variables: dict, events: EventManager) -> AsyncIterator[None]: ...
    async def close(self) -> None: ...
```

#### 1.2 Normalized models
- `AgentRunOptions`: deterministic, seed, strict, responses_use_instructions, budget {tokens, ms}, idempotency_key, trace_id, streaming_options, metadata.
- `AgentRunResult`: content (str|dict), usage {prompt_tokens, completion_tokens, total_tokens, cache_info}, model, elapsed_ms, provider_metadata, trace_id?, confidence?, final_json?.
- `PreparedRun`: provider/runtime‑specific compiled state.

### 2) Adapter: OpenAI Agents SDK

#### 2.1 Mapping
- Definition → OA Agent: `instructions`, `model`, `tools` (wrap our tools with `@function_tool`).
- Input → Runner: render `user_template.format(**variables)`; if `responses_use_instructions=True`, keep input minimal.
- Structured output: configure Responses `text.format` with root `additionalProperties=false`; set `strict=True` when model supports; always post‑validate with our schema validator.
- Params/capabilities: use capability registry to map `max_tokens`→`max_output_tokens`, omit/clamp temperature per model, forward seed only when supported.

#### 2.2 Streaming bridge
- Subscribe to OA events; forward to our `EventManager`:
  - `on_start(meta)` → StreamStartEvent
  - `on_delta(delta)` → StreamDeltaEvent (text/JSON via `StreamAdapter` + JSON handler when enabled)
  - `on_usage(usage)` → StreamUsageEvent (emit once; aggregate end‑of‑stream if absent)
  - `on_complete(result)` → StreamCompleteEvent (include final usage/elapsed)
  - `on_error(exc)` → StreamErrorEvent

#### 2.3 Determinism & budgets
- Determinism policy: clamp (`temperature`, `top_p`, etc.), forward `seed` when supported.
- Budgets: apply token/time budgets using `reliability/budget.py`; abort or return partial as per policy.

#### 2.4 Errors
- Map OA exceptions → `ProviderError` (with retry metadata via `ErrorClassifier`); schema mismatches → `SchemaError` with pointer path.

#### 2.5 Observability
- Metrics: `agent_runtime="openai_agents"`, `ttft_ms`, `chunks`, `tools_invoked`, `agent_loop_iters`, `handoffs`, `retry_count`, error category.
- Provider metadata: OA run/request IDs, any session/trace IDs.

### 3) Shared integration utilities
- `mapping.py` – schema/params/tools/error mapping helpers.
- `streaming.py` – typed event translation + JSON dedup + usage finalization.
- `errors.py` – integration error normalization.

### 4) Runner integration
- Extend `AgentRunner.run(..., options)` to accept `runtime`.
- Factory `get_agent_runtime(name)` → returns adapter instance; lazy import; helpful error if dependency missing.

### 5) Configuration
- Extras: `pip install steer-llm-sdk[openai-agents]`.
- Env: `OPENAI_API_KEY`; deterministic flags; budgets; streaming options.

### 6) Testing
- Unit: mapping (definition→agent), schema strict mapping + post‑validation, params per capabilities, error mapping, streaming bridge.
- Conformance: parity with provider adapters (generate, stream, usage, params, errors).
- Online smokes (opt‑in): GPT‑4.1 mini & GPT‑5 mini, strict JSON, determinism, tools.
- Performance: TTFT/throughput; event overhead <1ms.

### 7) Diagrams
- See `../diagrams/agents-runtime.mmd` for the runtime composition and event flow.


