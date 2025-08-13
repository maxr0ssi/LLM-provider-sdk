## Agents User Guide — OpenAI Responses API (GPT‑4.1 mini, GPT‑5 mini)

### What this guide covers
- How to define and run agents with structured outputs.
- How the SDK uses OpenAI Responses API for GPT‑4.1 mini and GPT‑5 mini.
- Determinism, idempotency, strict schema, and instructions mapping.
- Streaming with normalized event callbacks.

### Prerequisites
- Install and configure your OpenAI API key in environment variables.
- `pip install -r requirements.txt`

### Quick start (non‑streaming)
```python
from steer_llm_sdk.agents import AgentDefinition
from steer_llm_sdk.agents.runner.agent_runner import AgentRunner

agent = AgentDefinition(
    system="You extract structured facts as concise JSON.",
    user_template="Extract key facts from the following text: {text}",
    json_schema={
        "type": "object",
        "properties": {
            "facts": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["facts"],
        "additionalProperties": False
    },
    model="gpt-5-mini",
    parameters={"max_tokens": 256}
)

runner = AgentRunner()
result = await runner.run(
    agent,
    variables={"text": "The Eiffel Tower is in Paris and was built in 1889."},
    options={
        "deterministic": True,
        "metadata": {"strict": True, "responses_use_instructions": True},
        "idempotency_key": "example-1"
    }
)
print(result.content)  # Validated JSON
```

Notes:
- The SDK uses OpenAI Responses API when `json_schema` is provided and the model supports it.
- For GPT‑5 mini, `temperature` is omitted automatically (unsupported in Responses API).
- Root schema must include `additionalProperties: false`.

### Streaming with callbacks
```python
from steer_llm_sdk.agents import AgentDefinition
from steer_llm_sdk.agents.runner.agent_runner import AgentRunner

collected = []

async def on_start(meta):
    print("[start]", meta)

async def on_delta(delta):
    collected.append(delta)

async def on_usage(usage):
    print("[usage]", usage)

async def on_complete(result):
    print("[complete]", result.model, result.elapsed_ms)

agent = AgentDefinition(
    system="You output compact JSON with a 'summary' field.",
    user_template="Summarize: {text}",
    json_schema={
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
        "additionalProperties": False
    },
    model="gpt-4.1-mini",
    parameters={"max_tokens": 120}
)

runner = AgentRunner()
await runner.run(
    agent,
    variables={"text": "OpenAI introduced a unified Responses API..."},
    options={
        "streaming": True,
        "deterministic": True,
        "metadata": {
            "on_start": on_start,
            "on_delta": on_delta,
            "on_usage": on_usage,
            "on_complete": on_complete,
            "strict": True,
        }
    }
)

print("partial:", "".join(collected))
```

### Strict schema and instructions mapping
- **strict**: When `True`, the SDK sets `text.format.strict=true` and enforces tighter JSON adherence in Responses API.
- **responses_use_instructions**: When `True`, the SDK maps the first system message to `instructions` and removes it from `input`, matching OpenAI guidance.

Pass both via `options={"metadata": {"strict": True, "responses_use_instructions": True}}`.

### Determinism and seed
- Enable via `options={"deterministic": True}`.
- The SDK clamps parameters (e.g., `temperature=0` where supported) and forwards `seed` when supported by the model.
- Provide a seed with `parameters={"seed": 42}` in the agent definition or via options.

### Idempotency
- Provide a stable `idempotency_key` in options to deduplicate repeated requests during retries.

### Error handling
```python
from steer_llm_sdk.agents.errors import ProviderError, SchemaError

try:
    result = await runner.run(agent, variables={"text": "..."}, options={})
except SchemaError as e:
    # Output did not conform to schema
    ...
except ProviderError as e:
    # Transient provider failure (retry may help)
    ...
```

### Model notes
- **GPT‑5 mini**: Responses API supported; omit `temperature`. Great for strict structured outputs.
- **GPT‑4.1 mini**: Responses API supported; good cost/quality tradeoff for extraction and summaries.

### Troubleshooting
- Error requiring `additionalProperties=false`: add it at the schema root.
- "Unsupported parameter: temperature": do not send `temperature` when using GPT‑5 mini with Responses API.
- `KeyError` when formatting `user_template`: ensure all placeholders are present in `variables`.

### See also
- `docs/openai-responses-api.md` for deeper integration details.
- `docs/reports/NEXUS_SDK_MVP_REPORT.md` for architectural decisions and migration notes.


