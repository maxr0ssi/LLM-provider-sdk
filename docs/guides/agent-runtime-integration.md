# Agent Runtime Integration Guide

> This SDK is domain-neutral. Any role names or examples (e.g., "specialist", "scorer") are illustrative only.
> Note: Currently the runtime is pinned to `runtime="openai_agents"` with no fallback. Additional runtimes may be added in future releases via adapters.

This guide explains how to use the new agent runtime integration feature in the Steer LLM SDK, starting with OpenAI Agents SDK support.

## Overview

The agent runtime integration allows you to leverage provider-native agent frameworks (like OpenAI's Agents SDK) through our unified API. This provides:

- Native provider capabilities (tools, structured outputs, etc.)
- Normalized results and streaming events
- Consistent error handling and metrics
- Cost tracking and observability

## Installation

To use the OpenAI Agents runtime, install with the optional dependency:

```bash
pip install steer-llm-sdk[openai-agents]
```

## Basic Usage

### Non-Streaming Example

```python
from steer_llm_sdk.agents import AgentRunner, AgentDefinition

# Create agent definition
agent = AgentDefinition(
    system="You are a helpful assistant",
    user_template="Answer this question: {question}",
    model="openai:gpt-4o-mini",
    parameters={"temperature": 0.7, "max_tokens": 500}
)

# Create runner
runner = AgentRunner()

# Run with OpenAI Agents runtime
result = await runner.run(
    agent,
    {"question": "What is the capital of France?"},
    {"runtime": "openai_agents"}  # Specify runtime
)

print(result.content)
print(f"Tokens used: {result.usage}")
print(f"Cost: ${result.cost_usd:.4f}" if result.cost_usd else "Cost not available")
```

### Streaming Example

```python
from steer_llm_sdk.agents import AgentRunner, AgentDefinition

agent = AgentDefinition(
    system="You are a creative writer",
    user_template="Write a short story about: {topic}",
    model="openai:gpt-4o-mini",
    parameters={"temperature": 0.8, "max_tokens": 1000}
)

runner = AgentRunner()

# Define streaming callbacks
async def on_delta(event):
    print(event.delta, end="", flush=True)

async def on_complete(event):
    print(f"\n\nCompleted in {event.duration_ms}ms")

# Run with streaming
result = await runner.run(
    agent,
    {"topic": "a robot learning to paint"},
    {
        "runtime": "openai_agents",
        "streaming": True,
        "metadata": {
            "on_delta": on_delta,
            "on_complete": on_complete
        }
    }
)
```

## Structured Output with JSON Schema

The runtime supports JSON schema enforcement through OpenAI's Responses API:

```python
agent = AgentDefinition(
    system="Extract information from text",
    user_template="Extract key facts from: {text}",
    model="openai:gpt-4o-mini",
    json_schema={
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string", "enum": ["person", "place", "organization"]},
                        "description": {"type": "string"}
                    },
                    "required": ["name", "type"]
                }
            },
            "summary": {"type": "string"},
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]}
        },
        "required": ["entities", "summary"]
    }
)

result = await runner.run(
    agent,
    {"text": "Apple Inc. announced that Tim Cook will visit Paris next week."},
    {"runtime": "openai_agents", "metadata": {"strict": True}}
)

# Result.content will be the parsed JSON object
print(result.content["entities"])
print(result.content["summary"])
```

## Tool Usage

Define tools that the agent can use:

```python
from steer_llm_sdk.agents.models.agent_definition import Tool

def calculate(expression: str) -> float:
    """Safely evaluate mathematical expressions."""
    import ast
    import operator as op
    
    # Safe evaluation using AST
    allowed_ops = {
        ast.Add: op.add, ast.Sub: op.sub, 
        ast.Mult: op.mul, ast.Div: op.truediv
    }
    # ... implementation ...
    return result

agent = AgentDefinition(
    system="You are a helpful math assistant",
    user_template="Help me with: {problem}",
    model="openai:gpt-4.1-mini",
    tools=[
        Tool(
            name="calculate",
            description="Perform mathematical calculations",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            },
            handler=calculate
        )
    ]
)

result = await runner.run(
    agent,
    {"problem": "What is 15% of 280?"},
    {"runtime": "openai_agents"}
)
```

## Deterministic Mode (Semantics)

For reproducible outputs:

```python
result = await runner.run(
    agent,
    variables,
    {
        "runtime": "openai_agents",
        "deterministic": True,
        "metadata": {"seed": 42}
    }
)
```

- Seed propagation: when a provider does not support deterministic seeds, the SDK passes the seed but treats it as a no-op and emits a warning in logs/events.

## Idempotency and Advanced Options

### Idempotency Semantics

The SDK enforces idempotency at the runner/orchestrator boundary:

- Same `idempotency_key` + same payload → return stored result (upsert).
- Same `idempotency_key` + different payload → raise conflict (HTTP 409 equivalent) with a structured error.

### Budget Constraints

```python
result = await runner.run(
    agent,
    variables,
    {
        "runtime": "openai_agents",
        "budget": {
            "tokens": 1000,  # Max tokens to use
            "ms": 5000       # Max time in milliseconds
        }
    }
)
```

### Streaming Options and Event Schema

```python
from steer_llm_sdk.models.streaming import StreamingOptions

result = await runner.run(
    agent,
    variables,
    {
        "runtime": "openai_agents",
        "streaming": True,
        "metadata": {
            "streaming_options": StreamingOptions(
                enable_json_stream_handler=True,  # For structured output
                enable_usage_aggregation=True,    # Track token usage
                event_processor=my_processor      # Custom event processing
            )
        }
    }
)
```

Minimal event schema:

- `on_start`: `{ provider, model, request_id?, metadata? }`
- `on_delta`: `{ delta: str | dict, is_json?: bool, chunk_index }`
- `on_usage`: `{ usage: dict, is_estimated: bool, confidence?: float }`
- `on_complete`: `{ total_chunks, duration_ms, final_usage?, metadata? }`
- `on_error`: `{ error: { code, message, retriable? } }`

Security redaction hook: you may provide a callable to redact PII/secrets before events are emitted.

## Error Handling and Status Model

The runtime maps provider errors to normalized error types:

```python
from steer_llm_sdk.providers.base import ProviderError

try:
    result = await runner.run(agent, variables, {"runtime": "openai_agents"})
except ProviderError as e:
    print(f"Error: {e.message}")
    print(f"Status: {e.status_code}")
    print(f"Retryable: {e.is_retryable}")
    if e.retry_after:
        print(f"Retry after: {e.retry_after} seconds")
```

Standard status values: `accepted | running | succeeded | failed | partial`.
Standardized error payload: `{ code, message, provider?, retriable? }`.

## Metrics and Observability

When using a metrics sink, the runtime automatically tracks:

- Request/response latency
- Token usage (input/output/cached)
- Tool invocations
- Errors and retries
- Runtime dimension (`agent_runtime: "openai_agents"`)

```python
from steer_llm_sdk.observability import MyMetricsSink

runner = AgentRunner(metrics_sink=MyMetricsSink())

result = await runner.run(
    agent,
    variables,
    {"runtime": "openai_agents"}
)

# Metrics automatically recorded with agent_runtime dimension
```

## Model Support

The OpenAI Agents runtime works best with models that support advanced features:

- **Full Support**: `openai:gpt-4o-mini`, `openai:gpt-4.1-mini`, `openai:gpt-5-mini`, `openai:gpt-4o`, `openai:gpt-4.1`, `openai:gpt-5`
- **Partial Support**: `openai:gpt-3.5-turbo` (no JSON schema)
- **Special Models**: `openai:o4-mini` (requires temperature=1.0)

## Performance Considerations

- **Lazy Loading**: The OpenAI SDK is only imported when needed
- **Event Overhead**: Streaming events add < 1ms overhead
- **JSON Processing**: Structured output parsing is optimized
- **Cost Tracking**: Automatic cost calculation based on model pricing

## Future Runtimes

The architecture supports additional runtimes:

```python
# Future: Anthropic runtime
result = await runner.run(agent, variables, {"runtime": "anthropic_agents"})

# Future: Local runtime
result = await runner.run(agent, variables, {"runtime": "local_llama"})
```

## Migration Guide

If you're currently using the router directly, migration is simple:

```python
# Before
result = await runner.run(agent, variables, options)

# After (with runtime)
result = await runner.run(agent, variables, {**options, "runtime": "openai_agents"})
```

All existing options and callbacks continue to work.
