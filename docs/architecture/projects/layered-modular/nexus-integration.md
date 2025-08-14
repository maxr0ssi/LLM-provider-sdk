## Nexus Integration – Calling the SDK from the Orchestrator (A2A v1)

### Purpose
How the Nexus Orchestrator (OA) invokes the SDK for both Agent and Call paths, with event wiring to A2A v1 and provider‑agnostic behavior.

### Inputs Nexus should supply
- **model_id**: e.g., `gpt-5-mini`, `gpt-4.1-mini`, `claude-3-haiku-20240307`.
- **system** and **user_template**; plus **variables** for rendering the user message.
- Optional: **json_schema**, **tools**, **deterministic**, **seed**, **budgets** (`tokens`, `ms`), **idempotency_key**.
- Optional metadata: **strict**, **responses_use_instructions**, **reasoning**, **trace_id**.

### Event wiring (A2A v1)
- SDK callbacks map to Nexus A2A events:
  - `on_start(meta)` → START
  - `on_delta(delta)` → DELTA (text/JSON normalized)
  - `on_usage(usage)` → USAGE (emitted once if not available in‑stream)
  - `on_complete(result)` → COMPLETE (final `AgentResult`)
  - `on_error(error)` → ERROR (typed errors)

### Agent path (preferred for structured output / tools)
```python
from steer_llm_sdk.agents import AgentDefinition
from steer_llm_sdk.agents.runner.agent_runner import AgentRunner

# A2A → SDK callbacks
async def a2a_on_start(meta):
    emit_a2a("START", meta)

async def a2a_on_delta(delta):
    emit_a2a("DELTA", delta)

async def a2a_on_usage(usage):
    emit_a2a("USAGE", usage)

async def a2a_on_complete(result):
    emit_a2a("COMPLETE", {
        "model": result.model,
        "elapsed_ms": result.elapsed_ms,
        "usage": result.usage,
        "content": result.content,
    })

async def a2a_on_error(err):
    emit_a2a("ERROR", {"error": str(err)})


def make_agent(defn: dict) -> AgentDefinition:
    return AgentDefinition(
        system=defn["system"],
        user_template=defn["user_template"],
        json_schema=defn.get("json_schema"),
        model=defn["model_id"],
        parameters=defn.get("parameters", {}),
        tools=defn.get("tools"),
    )


async def run_agent(defn: dict, variables: dict, opts: dict):
    runner = AgentRunner()
    options = {
        "streaming": opts.get("streaming", False),
        "deterministic": opts.get("deterministic", False),
        "idempotency_key": opts.get("idempotency_key"),
        "budget": opts.get("budget"),  # {"tokens": int, "ms": int}
        "trace_id": opts.get("trace_id"),
        "metadata": {
            "on_start": a2a_on_start if opts.get("streaming") else None,
            "on_delta": a2a_on_delta if opts.get("streaming") else None,
            "on_usage": a2a_on_usage if opts.get("streaming") else None,
            "on_complete": a2a_on_complete if opts.get("streaming") else None,
            "on_error": a2a_on_error if opts.get("streaming") else None,
            # Responses API knobs (OpenAI)
            "strict": opts.get("strict"),
            "responses_use_instructions": opts.get("responses_use_instructions"),
            "reasoning": opts.get("reasoning"),
        },
    }

    agent = make_agent(defn)
    return await runner.run(agent, variables=variables, options=options)
```

Notes:
- If `json_schema` is present and the model supports native schema, the SDK selects OpenAI Responses API automatically (GPT‑4.1 mini, GPT‑5 mini). Root schema must include `additionalProperties: false`. For GPT‑5 mini, `temperature` is omitted.
- Deterministic mode clamps parameters and forwards `seed` when supported.
- `on_usage` is emitted once on completion when usage isn’t available in‑stream.

### Direct Call path (no schema/tools)
```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()
resp = await client.generate(
    messages="Write a short poem about dawn",
    llm_model_id="gpt-4o-mini",
    raw_params={"temperature": 0.4, "max_tokens": 120}
)
# resp.text, resp.usage
```

### Field mapping summary
- Inputs from Nexus → SDK:
  - `system`, `user_template`, `variables` → Agent messages
  - `model_id` → capability lookup and provider selection
  - `json_schema` → Responses API (when supported), else post‑validation
  - `deterministic`, `seed` → clamp + seed propagation
  - `budget` → `tokens` clamp and `ms` wall‑clock guard
  - `idempotency_key` → dedupe retries
  - `metadata.strict`, `metadata.responses_use_instructions` → Responses API flags
  - `trace_id` → propagated into result/metrics

- Outputs from SDK → Nexus:
  - `AgentResult.content` → text or validated JSON
  - `AgentResult.usage` → `{prompt_tokens, completion_tokens, total_tokens, cache_info}`
  - `AgentResult.elapsed_ms`, `AgentResult.model`, `trace_id`
  - Streaming events mapped to A2A via callbacks

### Error handling
- `ProviderError` → A2A ERROR (retryable policy handled in runner for non‑streaming path)
- `SchemaError` → A2A ERROR with details (often user/actionable)

### Optional: Provider‑native Agents (OpenAI Agents SDK)
- Keep the SDK agnostic. When targeting OpenAI’s native agent runtime, use the optional adapter pattern described in `docs/integrations/openai-agents-integration-plan.md`. The OA maps `AgentDefinition`/events to OpenAI Agents Runner.


