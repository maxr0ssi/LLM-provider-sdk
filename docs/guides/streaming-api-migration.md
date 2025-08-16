# Streaming API Migration Guide

## Overview

In recent versions of the Steer LLM SDK, we've split the streaming API to provide a cleaner, more predictable interface. The `return_usage` parameter has been removed from the `stream()` method in favor of a dedicated `stream_with_usage()` method.

## What Changed

### Before (Deprecated)
```python
# Old way - using return_usage parameter
response = await client.stream(
    "Hello, world!",
    "gpt-4o-mini",
    return_usage=True  # ❌ Deprecated
)
print(response.get_text())
print(response.usage)
```

### After (Current)
```python
# New way - using dedicated methods

# For pure streaming (yields chunks)
async for chunk in client.stream("Hello, world!", "gpt-4o-mini"):
    print(chunk, end="")

# For streaming with usage data (awaitable)
response = await client.stream_with_usage("Hello, world!", "gpt-4o-mini")
print(response.get_text())
print(response.usage)
```

## Migration Steps

### 1. Identify Usage Patterns

Look for code using `stream()` with `return_usage=True`:

```python
# Search your codebase for:
response = await client.stream(..., return_usage=True)
```

### 2. Replace with Appropriate Method

#### If you need usage data:
```python
# Before
response = await client.stream(messages, model, return_usage=True)

# After
response = await client.stream_with_usage(messages, model)
```

#### If you only need streamed text:
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

### 3. Update Error Handling

Both methods have the same error handling, but note the return types:

```python
try:
    # stream() returns an async generator
    async for chunk in client.stream(messages, model):
        process_chunk(chunk)
        
    # stream_with_usage() returns StreamingResponseWithUsage
    response = await client.stream_with_usage(messages, model)
    process_complete_response(response)
    
except Exception as e:
    handle_error(e)
```

## Benefits of the Split API

1. **Type Safety**: Clear return types for each method
2. **Performance**: Pure streaming doesn't collect usage overhead
3. **Clarity**: Method names clearly indicate their purpose
4. **Flexibility**: Choose the right tool for your needs

## Complete Examples

### Example 1: Simple Streaming
```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

# Just stream the response
async for chunk in client.stream(
    "Write a short poem",
    "gpt-4o-mini"
):
    print(chunk, end="", flush=True)
```

### Example 2: Streaming with Metrics
```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

# Get complete response with usage data
response = await client.stream_with_usage(
    "Explain quantum computing",
    "gpt-4o-mini",
    max_tokens=200
)

print(f"Response: {response.get_text()}")
print(f"Tokens used: {response.usage['total_tokens']}")
print(f"Cost: ${response.cost_usd:.6f}")
```

### Example 3: Conversation with Usage Tracking
```python
from steer_llm_sdk import SteerLLMClient, ConversationMessage, ConversationRole

client = SteerLLMClient()

messages = [
    ConversationMessage(
        role=ConversationRole.SYSTEM,
        content="You are a helpful assistant"
    ),
    ConversationMessage(
        role=ConversationRole.USER,
        content="What's the weather like?"
    )
]

# Stream conversation with usage data
response = await client.stream_with_usage(
    messages=messages,
    model="gpt-4o-mini"
)

print(f"Assistant: {response.get_text()}")
print(f"Cost for this conversation: ${response.cost_usd:.6f}")
```

## Deprecation Timeline

- The `return_usage` parameter is deprecated as of v0.2.0
- It will raise a deprecation warning in v0.3.0
- It will be removed entirely in v0.4.0

Please update your code to use the new API as soon as possible.