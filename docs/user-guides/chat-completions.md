## Chat Completions User Guide — Cross‑Provider (OpenAI, Anthropic, xAI)

### What this guide covers
- Using the high‑level `SteerLLMClient` for simple text generation and streaming.
- Passing provider‑specific parameters safely.
- Usage and cost data, with a focus on backward compatibility.

### Quick start (non‑streaming)
```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

# Minimal prompt (string)
resp = await client.generate("Write a 2‑line poem about the moon", llm_model_id="gpt-4o-mini")
print(resp.text)

# Multi‑turn messages
from steer_llm_sdk.models.conversation_types import ConversationMessage, ConversationRole
messages = [
    ConversationMessage(role=ConversationRole.SYSTEM, content="You are concise."),
    ConversationMessage(role=ConversationRole.USER, content="Explain qubits simply.")
]
resp = await client.generate(messages, llm_model_id="claude-3-haiku-20240307", temperature=0.2, max_tokens=200)
print(resp.text)
```

### Streaming
```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

async for chunk in client.stream("Stream a short inspirational quote", model="gpt-4o-mini", max_tokens=80):
    print(chunk, end="")
```

With usage collection:
```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()
stream = await client.stream_with_usage("Stream with usage example", model="gpt-4o-mini", max_tokens=120)

print(stream.text)
print(stream.usage)  # {prompt_tokens, completion_tokens, total_tokens, cache_info?}
```

### Provider‑specific parameters
Pass extra parameters via `raw_params` or `**kwargs`. The router normalizes per‑provider fields.
```python
# OpenAI example: top_p and presence_penalty
resp = await client.generate(
    "Invent an original riddle",
    llm_model_id="gpt-4o-mini",
    raw_params={"top_p": 0.9, "presence_penalty": 0.2, "max_tokens": 120}
)

# Anthropic example: system + stop sequences
resp = await client.generate(
    [
        {"role": "system", "content": "You are terse."},
        {"role": "user", "content": "List 3 facts about Jupiter"},
    ],
    llm_model_id="claude-3-haiku-20240307",
    raw_params={"stop": ["\n\n"], "max_tokens": 120}
)
```

### Usage and cost
Every response includes a normalized `usage` dict and, when possible, an exact `cost_usd` and `cost_breakdown`.
```python
resp = await client.generate("Hello", llm_model_id="gpt-4o-mini")
print(resp.cost_usd, resp.usage)
```

### Tips and gotchas
- For structured outputs on OpenAI models that support it, prefer the Agents + Responses API guide.
- Ensure your model IDs exist in the SDK registry (`client.get_available_models()`).
- Some providers/models use `max_output_tokens` vs `max_tokens`; the router handles this mapping.
- Token usage during streaming may only be available at the end; the SDK emits it once when available.

### When to use Chat Completions vs Agents
- **Chat Completions**: free‑form text, simple prompts, legacy flows, quick experiments.
- **Agents (Responses API)**: structured output, schema validation, deterministic runs, evented streaming, or tool execution.

### Troubleshooting
- Model not available: check `client.check_model_availability(model_id)` and your credentials.
- Unexpected parameters error: prefer `raw_params` so the router can normalize correctly.
- Streaming yields but no usage: use `stream_with_usage` or rely on final usage emission.


