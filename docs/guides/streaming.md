# Streaming Guide

This guide covers everything you need to know about streaming in the Steer LLM SDK, from basic usage to advanced patterns.

## Overview

The Steer LLM SDK provides a unified streaming architecture that works consistently across all providers (OpenAI, Anthropic, xAI). The streaming system is built on three core components:

1. **StreamingHelper** - High-level orchestration of streaming operations
2. **EventProcessor** - Pipeline for filtering and transforming events
3. **StreamAdapter** - Provider-specific normalization

## Quick Start

### Basic Streaming

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

# Stream text chunks
async for chunk in client.stream("Tell me a story", model="gpt-4o-mini"):
    print(chunk, end="", flush=True)
```

### Streaming with Usage Data

```python
# Get complete response with usage information
response = await client.stream_with_usage(
    "Explain quantum computing",
    model="gpt-4o-mini"
)

print(f"Response: {response.get_text()}")
print(f"Tokens: {response.usage['total_tokens']}")
print(f"Cost: ${response.cost_usd:.4f}")
```

## Configuration

### StreamingOptions

Control streaming behavior with `StreamingOptions`:

```python
from steer_llm_sdk.models.streaming import StreamingOptions, JSON_MODE_OPTIONS

# Custom streaming options
options = StreamingOptions(
    # Usage tracking
    enable_usage_aggregation=True,
    aggregator_type="auto",  # auto, tiktoken, character
    
    # JSON handling
    enable_json_stream_handler=True,
    validate_json_incrementally=True,
    
    # Connection settings
    connection_timeout=5.0,
    read_timeout=30.0,
    retry_on_connection_error=True,
    max_reconnect_attempts=3,
    
    # Performance
    chunk_size=1024,
    buffer_size=8192
)

response = await client.stream_with_usage(
    "Generate JSON data",
    model="gpt-4o-mini",
    streaming_options=options
)
```

### Preset Configurations

```python
from steer_llm_sdk.models.streaming import (
    JSON_MODE_OPTIONS,      # Optimized for JSON responses
    HIGH_THROUGHPUT_OPTIONS,  # For maximum performance
    LOW_LATENCY_OPTIONS      # For real-time applications
)

# Use preset for JSON streaming
response = await client.stream_with_usage(
    prompt="Generate product data",
    model="gpt-4o-mini",
    response_format={"type": "json_object"},
    streaming_options=JSON_MODE_OPTIONS
)
```

## Event Callbacks

Handle streaming events in real-time:

```python
from steer_llm_sdk.models.streaming import StreamingOptions

# Define event handlers
async def on_start():
    print("Stream started")

async def on_delta(text: str):
    print(f"Received: {text}")

async def on_usage(usage: dict):
    print(f"Usage: {usage}")

async def on_complete(final_text: str):
    print(f"Complete: {final_text}")

async def on_error(error: Exception):
    print(f"Error: {error}")

# Stream with callbacks
options = StreamingOptions(
    on_start=on_start,
    on_delta=on_delta,
    on_usage=on_usage,
    on_complete=on_complete,
    on_error=on_error
)

await client.stream_with_usage(
    "Tell me a joke",
    model="gpt-4o-mini",
    streaming_options=options
)
```

## JSON Mode Streaming

Stream and validate JSON responses incrementally:

```python
response = await client.stream_with_usage(
    "Generate a product listing with name, price, and description",
    model="gpt-4o-mini",
    response_format={"type": "json_object"},
    streaming_options=JSON_MODE_OPTIONS
)

# Access parsed JSON
data = response.get_json()
print(f"Product: {data['name']} - ${data['price']}")
```

## Advanced Patterns

### Custom Event Processing

```python
from steer_llm_sdk.streaming.processor import EventProcessor
from steer_llm_sdk.models.events import StreamEvent

# Create custom processor
processor = EventProcessor()

# Add filters
processor.add_filter(lambda event: event.type != "ping")

# Add transformers
def uppercase_transformer(event: StreamEvent) -> StreamEvent:
    if event.type == "text_delta" and event.delta:
        event.delta = event.delta.upper()
    return event

processor.add_transformer(uppercase_transformer)

# Use in streaming
async for event in processor.process(stream):
    if event.type == "text_delta":
        print(event.delta, end="")
```

### Streaming with Agents

```python
from steer_llm_sdk.agents.runner import AgentRunner

runner = AgentRunner()

# Stream agent responses
async for event in runner.stream(
    definition=agent_definition,
    variables={"query": "Calculate factorial of 10"},
    options={"streaming": True}
):
    if event.type == "delta":
        print(event.delta, end="")
    elif event.type == "tool_call":
        print(f"\n[Tool: {event.metadata['tool']}]")
```

## Error Handling

### Retry Configuration

```python
options = StreamingOptions(
    retry_on_connection_error=True,
    max_reconnect_attempts=3,
    reconnect_delay=1.0,
    preserve_partial_response=True  # Keep data from failed attempts
)

try:
    response = await client.stream_with_usage(
        "Long running task",
        model="gpt-4o-mini",
        streaming_options=options
    )
except Exception as e:
    print(f"Streaming failed after retries: {e}")
```

### Timeout Handling

```python
options = StreamingOptions(
    connection_timeout=5.0,   # Initial connection
    read_timeout=30.0,       # Between chunks
    total_timeout=300.0      # Overall limit
)
```

## Performance Optimization

### High Throughput Configuration

```python
from steer_llm_sdk.models.streaming import HIGH_THROUGHPUT_OPTIONS

# Process multiple streams concurrently
async def process_batch(prompts: list[str]):
    tasks = []
    for prompt in prompts:
        task = client.stream_with_usage(
            prompt,
            model="gpt-4o-mini",
            streaming_options=HIGH_THROUGHPUT_OPTIONS
        )
        tasks.append(task)
    
    responses = await asyncio.gather(*tasks)
    return responses
```

### Memory Management

```python
# Configure buffer sizes for large responses
options = StreamingOptions(
    chunk_size=4096,        # Larger chunks
    buffer_size=65536,      # Bigger buffer
    enable_compression=True  # Reduce memory usage
)
```

## Provider-Specific Features

### OpenAI

```python
# Use OpenAI-specific features
response = await client.stream_with_usage(
    "Generate code",
    model="gpt-4",
    streaming_options=StreamingOptions(
        # OpenAI supports usage in stream
        enable_usage_aggregation=False
    )
)
```

### Anthropic

```python
# Anthropic with caching
response = await client.stream_with_usage(
    messages=[
        {"role": "system", "content": "You are helpful", "cache_control": {"type": "ephemeral"}},
        {"role": "user", "content": "Hello"}
    ],
    model="claude-3-haiku-20240307"
)

# Check cache usage
if response.usage.get("cache_info"):
    print(f"Cached tokens: {response.usage['cache_info']['cached_tokens']}")
```

## Migration from Old API

If you're migrating from the old `return_usage` parameter:

```python
# Old way (deprecated)
response = await client.stream("Hello", "gpt-4", return_usage=True)

# New way
response = await client.stream_with_usage("Hello", "gpt-4")
```

For more details, see the [Streaming API Migration Guide](streaming-api-migration.md).

## Best Practices

1. **Use `stream()` for simple text streaming** - When you only need the text
2. **Use `stream_with_usage()` for complete data** - When you need usage, cost, or metadata
3. **Configure timeouts appropriately** - Set based on expected response length
4. **Handle errors gracefully** - Always wrap streaming in try-except blocks
5. **Use appropriate buffer sizes** - Larger buffers for high-throughput scenarios
6. **Enable compression for large responses** - Reduces memory usage
7. **Use callbacks for real-time processing** - Better than post-processing

## Related Documentation

- [Architecture Overview](../architecture/streaming.md) - Technical details of the streaming system
- [Event Reference](streaming-events.md) - Complete list of streaming events
- [Performance Guide](streaming-performance.md) - Optimization techniques