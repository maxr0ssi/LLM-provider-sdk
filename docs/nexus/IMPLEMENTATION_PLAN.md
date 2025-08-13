# Nexus Agent Framework Implementation Plan (SDK-only)

## Scope and Boundaries

This plan defines SDK primitives required to build and run agents with structured outputs, deterministic execution, optional local tools, and evented streaming. It is provider‑agnostic and does not include Orchestrator/OA logic, A2A protocol, Steer prompts, stage policies, or domain event names. The SDK exposes generic building blocks that any orchestrator can compose.

In scope (SDK):
- Agent primitives: definition, options, result
- Agent runner with streaming callbacks
- Provider adapters + capability registry
- Structured outputs via JSON schema validation
- Determinism (seed propagation, parameter clamping) and idempotency
- Local deterministic tool‑calling (optional)
- Typed errors and retry manager
- Metrics hooks (pluggable sink)

Out of scope (non‑SDK):
- OA orchestration, K×D policies, stage semantics (Static/Intent/Lightning/Dimensions/Referee)
- A2A HTTP contracts and domain event taxonomies
- Steer business logic or references

## Module Structure

```
steer_llm_sdk/
├── agents/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── agent_definition.py     # AgentDefinition, AgentOptions, AgentResult
│   │   └── capabilities.py         # ProviderCapabilities
│   ├── runner/
│   │   ├── __init__.py
│   │   ├── agent_runner.py         # Core runner (streaming + determinism + idempotency)
│   │   ├── execution_context.py    # Budgets (tokens/ms), trace, metadata
│   │   └── event_manager.py        # on_start/on_delta/on_usage/on_complete/on_error
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── tool_definition.py      # Tool model (local deterministic)
│   │   ├── tool_registry.py        # Registration + lookup
│   │   └── tool_executor.py        # Validation + execution
│   └── validators/
│       ├── __init__.py
│       ├── json_schema.py          # JSON schema validation helpers
│       └── result_validator.py     # Structured output validation
├── llm/
│   ├── providers/                  # OpenAI/Anthropic/xAI adapters
│   ├── registry.py                 # Add capability registry
│   └── router.py                   # Existing unified API (unchanged)
└── ...
```

## Core Models

```python
class AgentDefinition(BaseModel):
    system: str
    user_template: str
    json_schema: Optional[Dict[str, Any]] = None
    model: str
    parameters: Dict[str, Any] = {}
    tools: Optional[List[Tool]] = None
    version: str = "1.0"

class AgentOptions(BaseModel):
    streaming: bool = False
    deterministic: bool = False
    budget: Optional[Dict[str, Any]] = None  # { tokens?, ms? }
    metadata: Dict[str, Any] = {}
    idempotency_key: Optional[str] = None
    trace_id: Optional[str] = None

class AgentResult(BaseModel):
    content: Any  # Validated against json_schema if provided
    usage: Dict[str, Any]
    model: str
    elapsed_ms: int
    provider_metadata: Dict[str, Any]
    trace_id: Optional[str] = None
    confidence: Optional[float] = None

class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema
    handler: Callable
    deterministic: bool = True

class ProviderCapabilities(BaseModel):
    supports_json_schema: bool
    supports_streaming: bool
    supports_tools: bool
    supports_seed: bool
    supports_logprobs: bool
    max_context_length: int
    max_output_tokens: int
```

## Phases

### Phase 1: Core Primitives (Week 1)
- Implement `AgentDefinition`, `AgentOptions`, `AgentResult`.
- Add `ProviderCapabilities` and a capability registry for all configured providers.
- Implement JSON schema validator (`validators/json_schema.py`).

### Phase 2: Agent Runner + Events (Week 1–2)
- Implement `AgentRunner.run(definition, variables, options)`.
- Add `StreamAdapter` and `event_manager` with callbacks: `on_start`, `on_delta`, `on_usage`, `on_complete`, `on_error`.
- Keep event names generic; OA maps these to domain events outside the SDK.

### Phase 3: Provider Integration (Week 2)
- Map `response_format` to provider requests when `supports_json_schema=True` (e.g., OpenAI Responses API where available; fallback to chat completions otherwise).
- Post‑hoc schema validation for providers without native JSON schema.
- Deterministic mode: propagate `seed` if supported; clamp parameters (e.g., `temperature=0`) when `deterministic=True`.

#### Provider addition: GPT‑5 mini (OpenAI Responses API)
- Add model entry to `config/models.py` (e.g., key `"gpt-5-mini"`) with tokens, default temperature, context length, and pricing fields.
- Extend `LLMConstants.py` with input/output (and cached, if applicable) per‑1K pricing for GPT‑5 mini; wire into `registry.calculate_exact_cost` and `calculate_cache_savings`.
- Capability registry: mark `supports_json_schema=True`, `supports_seed=True`, `supports_streaming=True` for GPT‑5 mini.
- OpenAI adapter: when model is GPT‑5 mini and `json_schema` present, send via Responses API with `response_format={"type":"json_schema","json_schema":...}`; keep Chat Completions fallback for non‑schema requests if needed.
- Deterministic defaults: clamp temperature (≤0.1) when `deterministic=True` and pass `seed`.
- Tests: golden structured output fixtures; seeded determinism; streaming with usage; cost calculation including cache savings.

### Phase 4: Determinism & Idempotency (Week 2–3)
- Implement `IdempotencyManager` (in‑memory; pluggable interface) with `check_duplicate/store_result/cleanup_expired`.
  - Default TTL: 15 minutes for cached results
  - Configurable max cache size (default 1000 entries)
  - LRU eviction when size exceeded
- Enforce budgets/timeouts in `execution_context` and return partials or raise typed errors when exceeded.

### Phase 5: Tools Framework (Week 3)
- Implement `Tool` model, `tool_registry`, and `tool_executor` with JSON schema parameter validation.
- Tools are local, deterministic, and off by default; runner invokes tools only when defined and policy permits.
- Built-in tools for MVP:
  - `json_repair`: Attempt to fix malformed JSON (missing quotes, trailing commas)
  - `format_validator`: Validate output format against expected structure
  - `extract_json`: Extract JSON from mixed text/code output

### Phase 6: Errors & Retries (Week 3)
```python
class AgentError(Exception): ...
class ProviderError(AgentError): ...
class SchemaError(AgentError): ...
class ToolError(AgentError): ...
class TimeoutError(AgentError): ...
class BudgetExceededError(AgentError): ...

class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_factor: float = 2.0
    retryable_errors: List[Type[Exception]]

class RetryManager:
    async def execute_with_retry(self, func: Callable, config: RetryConfig): ...
```

### Phase 7: Metrics & Observability (Week 4)
```python
class AgentMetrics(BaseModel):
    request_id: str
    trace_id: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    retries: int
    error_class: Optional[str]
    tools_used: List[str]

class MetricsSink(Protocol):
    async def record(self, metrics: AgentMetrics): ...
    async def flush(self): ...

# Default implementation using OpenTelemetry (optional dependency)
class OTelMetricsSink:
    """Default metrics sink using OpenTelemetry. Only active if opentelemetry-api installed."""
    def __init__(self):
        try:
            from opentelemetry import metrics
            self.meter = metrics.get_meter("steer_llm_sdk")
            self.enabled = True
        except ImportError:
            self.enabled = False
    
    async def record(self, metrics: AgentMetrics):
        if self.enabled:
            # Record metrics to OTel
            pass
```
Integrate hooks in runner and provider boundaries.

### Phase 8: Docs, Examples, Tests (Week 4–5)
- Docs: API reference for agents, streaming callbacks, tools, capabilities.
- Examples: basic agent with schema; streaming with callbacks; deterministic mode + idempotency; local tool.
- Tests: unit (validators, runner, tools), integration (structured outputs per provider), determinism suite, retry/idempotency paths.
- Backward compatibility: existing `SteerLLMClient` API remains unchanged; agents are opt‑in.

## Usage Examples

### Basic Agent
```python
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition
from steer_llm_sdk.agents.runner.agent_runner import AgentRunner

agent = AgentDefinition(
    system="You are a helpful assistant that extracts structured data.",
    user_template="Extract key information from: {prompt}",
    json_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["summary", "key_points"]
    },
    model="gpt-4o-mini",
    parameters={"temperature": 0.2}
)

runner = AgentRunner()
result = await runner.run(
    agent,
    variables={"prompt": "Your text here..."},
    options={"deterministic": True}
)
print(result.content)
```

### Streaming with Callbacks
```python
async def on_delta(delta):
    print(delta)

async def on_complete(result):
    print(result)

await runner.run(
    agent,
    variables={"prompt": "Your text here..."},
    options={
        "streaming": True,
        "on_delta": on_delta,
        "on_complete": on_complete
    }
)
```

### Local Tool (optional)
```python
from steer_llm_sdk.agents.tools.tool_definition import Tool

def calculate_sum(numbers: list[int]) -> int:
    return sum(numbers)

sum_tool = Tool(
    name="calculate_sum",
    description="Calculate the sum of a list of numbers",
    parameters={
        "type": "object",
        "properties": {"numbers": {"type": "array", "items": {"type": "integer"}}},
        "required": ["numbers"]
    },
    handler=calculate_sum
)

agent.tools = [sum_tool]
```

## Success Criteria

1. Backward compatible: existing SDK interfaces unchanged; all current tests pass.
2. Provider‑agnostic: no OA/A2A/Steer references; capability‑driven behavior.
3. Reliability: deterministic runs stable; schema validation enforced; retryable failures recovered.
4. Observability: normalized usage and metrics hooks available.
5. Documentation and examples cover common patterns.
6. Test coverage ≥ 90% for new modules.

## Codebase Cleanup (detailed, actionable)

### 1) Logging hygiene (providers and core)
- Files: `steer_llm_sdk/llm/providers/openai.py`, `anthropic.py`, `xai.py`
- Actions:
  - Replace all `print(...)` (including emoji debug) with `logger.debug/info/warning` using module loggers.
  - Guard verbose logs behind a `SDK_DEBUG` env or logger level.
  - Ensure no prints in library code paths; keep prints only in `examples/` and CLI.
- Acceptance: zero `print(` in `steer_llm_sdk/` except CLI; debug output controlled by log level.

### 2) Determinism policy centralization
- Files: new `steer_llm_sdk/agents/runner/determinism.py` (or inside `agent_runner.py`).
- Actions:
  - Implement `apply_deterministic_policy(params, capabilities)` to clamp `temperature`, `top_p`, etc.
  - Source provider/model constraints from capability registry (e.g., `o4-mini` forces `temperature=1.0`).
  - Propagate `seed` only when `supports_seed=True`.
- Acceptance: no model‑name heuristics scattered in providers; unit tests cover policy mapping.

### 3) Capability registry (single source of truth)
- Files: `steer_llm_sdk/llm/registry.py` (extend) or new `steer_llm_sdk/llm/capabilities.py`.
- Actions:
  - For each `config/models.py` entry, derive `ProviderCapabilities` (json_schema/seed/streaming/tools/logprobs, context, max_output).
  - Replace conditionals like `if model_lower.startswith("o4-mini")` in providers with capability checks.
- Acceptance: providers consult capabilities; fewer hardcoded model branches; tests assert capabilities for each model (incl. GPT‑5 mini).

### 4) Provider adapters consistency
- OpenAI (`openai.py`):
  - Add Responses API path for schema mode; keep Chat fallback; unify `max_tokens` vs `max_completion_tokens` via capability flag (e.g., `uses_max_completion_tokens`).
  - Move prompt caching logs to `logger.debug`.
  - Ensure `response_format` and `seed` pass‑through only when supported.
- Anthropic (`anthropic.py`):
  - Remove prints; standardize usage keys; mark `supports_json_schema=False` (post‑validate only).
  - Clamp via determinism policy; handle system caching logs as debug.
- xAI (`xai.py`):
  - Add `seed` passthrough if/when supported; otherwise ignore under determinism.
  - Keep estimated usage path but clearly mark `usage.cache_info={}` and document limitations.
- Acceptance: all adapters expose `generate`, `generate_stream`, `generate_stream_with_usage` with consistent tuple protocol; no stray prints; schema path only on supported models.

### 5) Usage shape and cost calculation unification
- Files: `steer_llm_sdk/models/generation.py`, `steer_llm_sdk/llm/registry.py`.
- Actions:
  - Define expected `usage` keys: `prompt_tokens`, `completion_tokens`, `total_tokens`, optional `cache_info`.
  - In `registry.calculate_exact_cost`, prefer per‑model `input_cost_per_1k_tokens` and `output_cost_per_1k_tokens` from `config/models.py`; deprecate hardcoded model `if/elif` branches.
  - Keep `LLMConstants.py` as historical defaults only; source of truth is model config.
- Acceptance: cost calc uses model config fields; usage dicts consistent across providers; tests updated.

### 6) JSON schema validation path
- Files: `steer_llm_sdk/agents/validators/json_schema.py`, `result_validator.py`, `agents/runner/agent_runner.py`.
- Actions:
  - Implement strict validation of final content when `json_schema` is provided.
  - For providers without native schema mode, parse text → JSON → validate → raise `SchemaError` with helpful path info; add an optional `schema_repair` tool hook (Phase 5).
- Acceptance: unit tests for valid/invalid cases; parse‑fail rate tracked; clear error messages.

### 7) Streaming normalization
- Files: `agents/runner/event_manager.py` (new), `llm/providers/*` (adapters), `agents/runner/agent_runner.py`.
- Actions:
  - Normalize streaming to generic callbacks: `on_start`, `on_delta`, `on_usage`, `on_complete`, `on_error`.
  - Provide `StreamAdapter` to map provider deltas to `{ type: "text", value: str }` or `{ type: "json", value: dict }`.
- Acceptance: examples show identical callback signatures across providers; tests cover streaming with usage.

### 8) Idempotency and budgets
- Files: `agents/runner/execution_context.py` (budgets), new `idempotency.py`.
- Actions:
  - Implement `IdempotencyManager` in‑memory; document pluggable interface.
  - Enforce `budget.ms` and `budget.tokens` in runner; return partial or raise `TimeoutError/BudgetExceededError`.
- Acceptance: seeded reruns dedupe; budget tests pass; no provider‑level idempotency assumptions.

### 9) Error taxonomy and API separation
- Files: new `agents/errors.py`; refactor `llm/router.py`.
- Actions:
  - Introduce typed errors and use them in providers and runner; remove generic `Exception` where feasible.
  - Separate service layer from FastAPI: move FastAPI endpoints into `api.py`; keep `LLMRouter` free of HTTP types (return results/raise typed errors). The SDK remains framework‑agnostic.
- Acceptance: library use throws typed errors; FastAPI layer wraps into HTTP responses; no FastAPI imports in core service classes.

### 10) Pydantic v2 alignment and typing
- Files: all models in `steer_llm_sdk/models/*`, new agent models.
- Actions:
  - Replace legacy `class Config: extra = "allow"` with `model_config = ConfigDict(extra="allow")`.
  - Add explicit types for maps (e.g., `Dict[str, int | float | dict]`) where used.
  - Avoid `Any` unless necessary; document pass‑through fields.
- Acceptance: no pydantic deprecation warnings; mypy/pyright clean for new modules.

### 11) Provider API surface and docs
- Files: provider adapters and docs.
- Actions:
  - Document which fields are honored per provider (seed, response_format, max tokens field name, streaming usage availability).
  - Capability registry used in runner to choose safe paths.
- Acceptance: README/docs section listing capabilities per model/provider; examples align.

### 12) Module boundaries and imports
- Files: `llm/router.py` (refactor), new `api.py`.
- Actions:
  - Ensure importing the SDK does not eagerly import FastAPI or heavy deps unless the API module is imported explicitly.
- Acceptance: library import time reduced; no side‑effects from importing core modules.

### 13) Examples and CLI scope
- Files: `examples/*`, `steer_llm_sdk/cli.py`.
- Actions:
  - Keep `print` usage in examples/CLI only; ensure examples demonstrate streaming callbacks, schema validation, determinism, and cost reporting.
- Acceptance: examples run green; demonstrate new features succinctly.

### 14) Test and CI hygiene
- Files: `tests/*`.
- Actions:
  - Add unit tests for: capability mapping, determinism policy, schema validation, error taxonomy, idempotency, streaming adapter.
  - Add integration tests for OpenAI (schema mode) and Anthropic (post‑validation) with golden fixtures.
  - Add lint/type checks in CI.
- Acceptance: tests pass locally and in CI; coverage target met for new modules.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Provider API differences | Medium | Capability registry + adapters + post‑validation |
| JSON parse failures | Medium | Native schema mode when available; strict post‑validation otherwise |
| Determinism variance | Low | Clamp parameters, propagate seed, seed‑aware tests |
| Performance overhead | Low | Lightweight adapters, event throttling, optional tools |

## Timeline

- Week 1: Core models + validators + capability registry
- Week 1–2: Agent runner + streaming callbacks
- Week 2: Provider schema integration + deterministic mode + GPT‑5 mini wiring
- Week 2–3: Idempotency + budgets/timeouts
- Week 3: Tools framework (local deterministic)
- Week 3: Typed errors + retries
- Week 4: Metrics hooks + docs/examples/tests


