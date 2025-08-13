## Examples – Layered Modular SDK

### 1) Direct call (OpenAI, Chat path)
```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()
resp = await client.generate("Write a limerick about Mars", llm_model_id="gpt-4o-mini", raw_params={"top_p": 0.9, "max_tokens": 120})
print(resp.text)
print(resp.usage)
```

### 2) Agent with schema (OpenAI Responses API)
```python
from steer_llm_sdk.agents import AgentDefinition
from steer_llm_sdk.agents.runner.agent_runner import AgentRunner

agent = AgentDefinition(
    system="You produce JSON with 'summary' and 'key_points'",
    user_template="Summarize: {text}",
    json_schema={
        "type": "object",
        "properties": {"summary": {"type": "string"}, "key_points": {"type": "array", "items": {"type": "string"}}},
        "required": ["summary", "key_points"],
        "additionalProperties": False
    },
    model="gpt-5-mini",
    parameters={"max_tokens": 256}
)

result = await AgentRunner().run(agent, variables={"text": "OpenAI released ..."}, options={"deterministic": True, "metadata": {"strict": True, "responses_use_instructions": True}})
print(result.content)
```

### 3) Agent streaming (Anthropic fallback + post‑validation)
```python
agent = AgentDefinition(
    system="Extract names as JSON array",
    user_template="From the text list names: {text}",
    json_schema={"type": "array", "items": {"type": "string"}, "additionalProperties": False},
    model="claude-3-haiku-20240307",
    parameters={"max_tokens": 128}
)

async def on_delta(d):
    print(d, end="")

await AgentRunner().run(
    agent,
    variables={"text": "Alice met Bob and Carol."},
    options={"streaming": True, "metadata": {"on_delta": on_delta}}
)
```

### 4) Add a new model (capability entry)
```python
# capabilities.registry.py
add_model("vendor-x-mini", ProviderCapabilities(
    supports_json_schema=False,
    supports_seed=True,
    supports_streaming=True,
    token_param_name="max_tokens",
))
```

### 5) Optional adapter usage (OpenAI Agents SDK) – outside core
```python
# pip install openai-agents
content = await run_with_openai_agents(definition=agent, variables={"text": "..."}, strict=True)
```


