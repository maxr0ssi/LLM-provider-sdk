# Streaming Guide

Complete guide to streaming in the Steer LLM SDK.

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

Control streaming behavior with `StreamingOptions`:

```python
from steer_llm_sdk.models.streaming import StreamingOptions

options = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="auto",  # auto, tiktoken, character
    enable_json_stream_handler=True,
    connection_timeout=5.0,
    read_timeout=30.0,
    retry_on_connection_error=True,
    max_reconnect_attempts=3
)

response = await client.stream_with_usage(
    "Generate data",
    model="gpt-4o-mini",
    streaming_options=options
)
```

### Preset Configurations

```python
from steer_llm_sdk.models.streaming import (
    JSON_MODE_OPTIONS,
    HIGH_THROUGHPUT_OPTIONS,
    LOW_LATENCY_OPTIONS
)

# Use preset for JSON streaming
response = await client.stream_with_usage(
    "Generate product data",
    model="gpt-4o-mini",
    response_format={"type": "json_object"},
    streaming_options=JSON_MODE_OPTIONS
)
```

## Event Callbacks

Handle streaming events in real-time:

```python
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

Stream and validate JSON responses:

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

## Error Handling

### Retry Configuration

```python
options = StreamingOptions(
    retry_on_connection_error=True,
    max_reconnect_attempts=3,
    reconnect_delay=1.0,
    preserve_partial_response=True
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
    read_timeout=30.0,        # Between chunks
    total_timeout=300.0       # Overall limit
)
```

## Provider-Specific Features

### OpenAI

```python
response = await client.stream_with_usage(
    "Generate code",
    model="gpt-4",
    streaming_options=StreamingOptions(
        enable_usage_aggregation=False  # OpenAI provides usage in stream
    )
)
```

### Anthropic with Caching

```python
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

The `return_usage` parameter has been removed. Use dedicated methods instead:

### Before (Deprecated)

```python
# Old way - using return_usage parameter
response = await client.stream(
    "Hello, world!",
    "gpt-4o-mini",
    return_usage=True  # Deprecated
)
```

### After (Current)

```python
# For pure streaming (yields chunks)
async for chunk in client.stream("Hello, world!", "gpt-4o-mini"):
    print(chunk, end="")

# For streaming with usage data (awaitable)
response = await client.stream_with_usage("Hello, world!", "gpt-4o-mini")
print(response.get_text())
print(response.usage)
```

### Migration Steps

1. Find code using `stream()` with `return_usage=True`
2. Replace with `stream_with_usage()` if you need usage data
3. Replace with `stream()` iterator if you only need text chunks

#### If you need usage data:

```python
# Before
response = await client.stream(messages, model, return_usage=True)

# After
response = await client.stream_with_usage(messages, model)
```

#### If you only need text:

```python
# Before
response = await client.stream(messages, model, return_usage=False)
text = response.get_text()

# After (more efficient)
text_chunks = []
async for chunk in client.stream(messages, model):
    text_chunks.append(chunk)
text = ''.join(text_chunks)
```

### Benefits of Split API

1. **Type Safety**: Clear return types for each method
2. **Performance**: Pure streaming doesn't collect usage overhead
3. **Clarity**: Method names clearly indicate their purpose

### Deprecation Timeline

- `return_usage` deprecated in v0.2.0
- Removed entirely in v0.3.0

## Best Practices

1. Use `stream()` for simple text streaming when you only need the text
2. Use `stream_with_usage()` for complete data (usage, cost, metadata)
3. Configure timeouts appropriately based on expected response length
4. Handle errors gracefully with try-except blocks
5. Use appropriate buffer sizes for high-throughput scenarios
6. Use callbacks for real-time processing instead of post-processing
