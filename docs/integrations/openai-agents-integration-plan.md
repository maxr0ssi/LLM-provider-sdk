## Optional Integration Plan: OpenAI Agents SDK

### Objective
Provide an optional adapter to leverage the OpenAI Agents SDK for OpenAI models (GPT‑4.1 mini, GPT‑5 mini) while keeping this SDK provider‑agnostic and free of vendor‑specific runtime semantics.

References:
- OpenAI Agents – Guide: [platform.openai.com/docs/guides/agents](https://platform.openai.com/docs/guides/agents)
- OpenAI Agents SDK – Context management: [openai.github.io/openai-agents-python/context/](https://openai.github.io/openai-agents-python/context/)

### Scope
- In scope: a thin adapter that maps our agent primitives and callbacks to OpenAI Agents SDK constructs for OpenAI models only.
- Out of scope: introducing `openai-agents` as a hard dependency of this SDK, or changing core provider‑agnostic behavior.

### Dependency strategy
- Keep the core SDK as‑is. Do not add `openai-agents` to `requirements.txt`.
- Offer as an optional dependency (consumer project installs it):
  - `pip install openai-agents`
  - Integration lives outside core SDK (recommended: main/orchestrator repo) or under an `integrations/` module that is not imported by default.

### High‑level design
- Adapter module (example path for consumer): `integrations/openai_agents_adapter.py`
- Responsibilities:
  - Translate `AgentDefinition` → OpenAI `Agent` (instructions/system, model, tool specs).
  - Map `user_template`/variables → input text (and retain `instructions` mapping per `responses_use_instructions`).
  - Serialize JSON schema to OpenAI Responses format (`text.format`), with `additionalProperties=false` root.
  - Bridge streaming events: OpenAI Runner events → our `on_start/on_delta/on_usage/on_complete/on_error` callbacks.
  - Context bridging: expose optional local context object similar to `RunContextWrapper` for tool functions.
  - Determinism: set seed, clamp parameters; omit unsupported fields (e.g., `temperature` on GPT‑5 mini).
  - Error mapping: map OpenAI Agents exceptions to our `ProviderError`/`SchemaError` where appropriate.

### Mapping summary
- System/instructions:
  - If `responses_use_instructions=True` → map `definition.system` to Agents `instructions` and keep `input` minimal.
  - Else include system as first message in `input`.
- Input:
  - Render `definition.user_template.format(**variables)` to the runner `input`.
- Model:
  - Use `definition.model` (e.g., `gpt-5-mini`, `gpt-4.1-mini`).
- Structured output:
  - If `json_schema` provided → use Responses API JSON schema via `text.format` with `strict` when set.
- Params:
  - `max_tokens` → `max_output_tokens` when required by model capability; omit `temperature` for GPT‑5 mini.
- Tools:
  - Convert our deterministic local tools to `@function_tool` definitions. Parameter schema comes from our tool schema or `schema_from_callable`.
- Streaming:
  - Translate Agents SDK streaming events to our normalized deltas and usage emission.

### Example (consumer‑side, conceptual)
```python
# pip install openai-agents
from agents import Agent as OAAgent, Runner as OARunner, function_tool

from steer_llm_sdk.agents import AgentDefinition
from steer_llm_sdk.agents.validators.json_schema import validate_json_schema


def to_openai_agent(defn: AgentDefinition):
    # Map tools
    oa_tools = []
    for t in defn.tools or []:
        @function_tool(name=t.name, description=t.description)
        async def tool_wrapper(input: dict):
            return t.handler(**input)
        oa_tools.append(tool_wrapper)

    # Build agent (instructions/system)
    agent = OAAgent(
        name="SDKAgent",
        instructions=defn.system,
        tools=oa_tools,
        model=defn.model,
        # Additional model settings if needed
    )
    return agent


async def run_with_openai_agents(defn: AgentDefinition, variables: dict, strict: bool = True):
    agent = to_openai_agent(defn)
    user_input = defn.user_template.format(**variables)

    # Runner call; adapter ensures Responses JSON schema & strict mapping
    result = await OARunner.run(starting_agent=agent, input=user_input)

    content = result.final_output
    if defn.json_schema:
        # Best‑effort validation (OpenAI already enforced if strict schema was used)
        validate_json_schema(content, defn.json_schema)
    return content
```

### Streaming adapter
- Subscribe to OpenAI Agents SDK streaming events and forward to our callbacks:
  - `on_start(meta)` when stream begins.
  - `on_delta(delta)` for text/JSON partials.
  - `on_usage(usage)` once when available.
  - `on_complete(result)` at final aggregation.
  - `on_error(exc)` on failure.

### Determinism & idempotency
- Determinism: enforce clamp policy and forward `seed` for supported models; omit `temperature` on GPT‑5 mini.
- Idempotency: handled by caller or use our in‑memory `IdempotencyManager` around the adapter to dedupe retries.

### Error handling
- Wrap OpenAI Agents exceptions into our typed errors where feasible:
  - Transport/transient → `ProviderError`
  - Schema mismatch (post‑hoc) → `SchemaError`

### Testing plan
- Smokes (online):
  - GPT‑4.1 mini & GPT‑5 mini structured output with `strict=True`.
  - Deterministic runs (seeded) produce consistent outputs.
  - Streaming path emits normalized deltas and final usage.
  - Tool call with simple deterministic function.
- Offline: adapter unit tests for mapping logic.

### Rollout plan
1) Draft adapter in consumer repo (`integrations/`), not in SDK core.
2) Add examples and a short usage guide.
3) Wire smoke tests behind OpenAI creds; keep optional in CI.
4) Iterate based on usage and stability.

### Risks & mitigations
- Vendor lock‑in creeping into core: keep adapter separate and optional.
- API drift in OpenAI Agents SDK: version‑pin in consumer and encapsulate mapping in one place.
- Inconsistent usage data in stream: emit usage on completion when not present in‑stream.

### Next steps
- Approve optional integration strategy.
- Implement the adapter in the main/orchestrator repo with the mapping above.
- Add a short “Integration Guide” referencing this plan.


