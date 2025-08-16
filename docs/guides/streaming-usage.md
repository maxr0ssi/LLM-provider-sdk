# Streaming Usage Guide

This guide covers how to use the unified streaming architecture in the Steer LLM SDK for various use cases.

## Table of Contents

1. [Basic Streaming](#basic-streaming)
2. [Streaming with Usage Data](#streaming-with-usage-data)
3. [Event Callbacks](#event-callbacks)
4. [JSON Mode Streaming](#json-mode-streaming)
5. [Advanced Event Processing](#advanced-event-processing)
6. [Error Handling](#error-handling)
7. [Performance Optimization](#performance-optimization)
8. [Provider-Specific Considerations](#provider-specific-considerations)

## Basic Streaming

The simplest way to stream responses is using the `stream` method:

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

# Stream text chunks
async for chunk in client.stream("Tell me a story", model="gpt-4"):
    print(chunk, end="", flush=True)
```

This yields raw text chunks as they arrive from the provider.

## Streaming with Usage Data

To collect usage data (token counts) along with the streamed text:

```python
# Stream and collect usage data
response = await client.stream_with_usage(
    "Write a haiku about coding",
    model="gpt-4",
    max_tokens=50
)

# Access the complete text
print("Text:", response.get_text())

# Access usage data
print("Tokens used:", response.usage)
# Output: {'prompt_tokens': 12, 'completion_tokens': 17, 'total_tokens': 29}

# Access cost information if available
if response.cost_usd:
    print(f"Cost: ${response.cost_usd:.4f}")
```

## Event Callbacks

You can register callbacks to receive streaming events as they occur:

```python
# Define event handlers
async def on_start(event):
    print(f"[STARTED] Model: {event.model}, Provider: {event.provider}")

async def on_delta(event):
    print(f"[CHUNK {event.chunk_index}] {event.delta.get_text()}")

async def on_usage(event):
    print(f"[USAGE] {event.usage}")

async def on_complete(event):
    print(f"[COMPLETE] Duration: {event.metadata.get('duration_ms')}ms")

async def on_error(event):
    print(f"[ERROR] {event.error_type}: {event.error}")

# Stream with callbacks
response = await client.stream_with_usage(
    "Explain quantum computing",
    model="gpt-4",
    on_start=on_start,
    on_delta=on_delta,
    on_usage=on_usage,
    on_complete=on_complete,
    on_error=on_error
)
```

## JSON Mode Streaming

For structured output, use JSON mode with automatic parsing:

```python
from steer_llm_sdk.models.streaming import JSON_MODE_OPTIONS

# Generate structured data
response = await client.stream_with_usage(
    "Generate a JSON object with user data including name, age, and email",
    model="gpt-4",
    response_format={"type": "json_object"},
    streaming_options=JSON_MODE_OPTIONS
)

# Get the parsed JSON
json_data = response.get_json()
print(json_data)
# Output: {'name': 'John Doe', 'age': 30, 'email': 'john@example.com'}

# The raw text is still available
print(response.get_text())
```

## Advanced Event Processing

For more control over event processing, use a custom EventProcessor:

```python
from steer_llm_sdk.streaming.processor import create_event_processor
from steer_llm_sdk.models.streaming import StreamingOptions

# Create a custom event processor
processor = create_event_processor(
    add_correlation=True,      # Add correlation IDs
    add_timestamp=True,        # Add timestamps to events
    add_metrics=True,          # Track streaming metrics
    event_types=["delta", "usage"],  # Filter specific events
    background=False           # Process synchronously
)

# Use with streaming options
options = StreamingOptions(
    event_processor=processor,
    enable_usage_aggregation=True
)

response = await client.stream_with_usage(
    "Generate content",
    model="gpt-4",
    streaming_options=options
)
```

### Custom Event Transformers

You can create custom transformers to modify events:

```python
from steer_llm_sdk.streaming.processor import EventTransformer
from steer_llm_sdk.models.events import StreamDeltaEvent

class ContentFilterTransformer(EventTransformer):
    """Filter sensitive content from streaming responses."""
    
    def __init__(self, banned_words):
        self.banned_words = set(w.lower() for w in banned_words)
    
    async def transform(self, event):
        if isinstance(event, StreamDeltaEvent):
            text = event.delta.get_text()
            if text:
                # Simple word filtering
                words = text.split()
                filtered = [
                    "***" if w.lower() in self.banned_words else w 
                    for w in words
                ]
                event.delta.value = " ".join(filtered)
        return event

# Create processor with custom transformer
processor = create_event_processor()
processor.add_transformer(ContentFilterTransformer(["badword"]))

options = StreamingOptions(event_processor=processor)
```

## Error Handling

The streaming architecture provides robust error handling:

```python
from steer_llm_sdk.providers.base import ProviderError

try:
    response = await client.stream_with_usage(
        "Generate text",
        model="gpt-4",
        max_tokens=100
    )
except ProviderError as e:
    print(f"Provider error: {e}")
    print(f"Provider: {e.provider}")
    print(f"Status code: {e.status_code}")
    print(f"Is retryable: {e.is_retryable}")
    
    # Handle specific error types
    if e.status_code == 429:
        print("Rate limit exceeded, please retry later")
    elif e.is_retryable:
        print("Transient error, retrying...")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Handling Streaming Interruptions

```python
collected_text = []

async def safe_stream():
    try:
        async for chunk in client.stream("Generate a long story", model="gpt-4"):
            collected_text.append(chunk)
            print(chunk, end="", flush=True)
    except asyncio.CancelledError:
        print("\n[Stream cancelled]")
        # Save partial response
        partial = "".join(collected_text)
        print(f"Collected {len(partial)} characters before cancellation")
    except Exception as e:
        print(f"\n[Stream error: {e}]")

# Run with timeout
try:
    await asyncio.wait_for(safe_stream(), timeout=5.0)
except asyncio.TimeoutError:
    print("\n[Stream timed out]")
```

## Performance Optimization

### High-Performance Streaming

For maximum throughput with minimal overhead:

```python
from steer_llm_sdk.models.streaming import StreamingOptions

# Optimize for speed
fast_options = StreamingOptions(
    enable_usage_aggregation=False,    # Skip token counting
    enable_json_stream_handler=False,  # No JSON parsing
    connection_timeout=3.0,            # Fail fast
    read_timeout=20.0,                 # Reasonable timeout
    retry_on_connection_error=False    # No retries
)

# Use simple streaming without usage tracking
async for chunk in client.stream(
    "Generate text quickly",
    model="gpt-4",
    streaming_options=fast_options
):
    process_chunk(chunk)  # Your processing logic
```

### Batch Processing with Streaming

Process multiple requests concurrently:

```python
import asyncio

async def stream_request(prompt, model="gpt-4"):
    """Stream a single request."""
    chunks = []
    async for chunk in client.stream(prompt, model=model):
        chunks.append(chunk)
    return "".join(chunks)

# Process multiple prompts concurrently
prompts = [
    "Write a haiku about Python",
    "Write a haiku about JavaScript",
    "Write a haiku about Rust"
]

# Stream all concurrently
tasks = [stream_request(p) for p in prompts]
results = await asyncio.gather(*tasks)

for prompt, result in zip(prompts, results):
    print(f"\nPrompt: {prompt}")
    print(f"Result: {result}")
```

### Memory-Efficient Streaming

For processing large responses without storing everything in memory:

```python
async def process_large_stream():
    """Process a large stream without storing all content."""
    word_count = 0
    char_count = 0
    
    async for chunk in client.stream(
        "Write a 1000-word essay",
        model="gpt-4",
        max_tokens=2000
    ):
        # Process chunk without storing
        words = chunk.split()
        word_count += len(words)
        char_count += len(chunk)
        
        # Could write to file, send to another service, etc.
        await process_chunk_externally(chunk)
    
    print(f"Processed {word_count} words, {char_count} characters")
```

## Provider-Specific Considerations

### OpenAI Streaming

```python
# OpenAI-specific optimizations
from steer_llm_sdk.models.streaming import StreamingOptions

openai_options = StreamingOptions(
    enable_usage_aggregation=True,
    prefer_tiktoken=True,  # Use accurate token counting
    aggregator_type="tiktoken"
)

response = await client.stream_with_usage(
    "Generate text",
    model="gpt-4",
    streaming_options=openai_options
)
```

### Anthropic Streaming

```python
# Anthropic-specific settings
anthropic_options = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="character",  # Anthropic doesn't support tiktoken
    read_timeout=60.0  # Anthropic can be slower
)

response = await client.stream_with_usage(
    "Generate text",
    model="claude-3-opus",
    streaming_options=anthropic_options
)
```

### xAI Streaming

```python
# xAI-specific configuration
xai_options = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="character",
    connection_timeout=10.0,  # xAI may need more time
    read_timeout=45.0
)

response = await client.stream_with_usage(
    "Generate text",
    model="grok-2",
    streaming_options=xai_options
)
```

## Best Practices

1. **Choose the right method**: Use `stream()` for simple text streaming, `stream_with_usage()` when you need token counts or cost data.

2. **Handle errors gracefully**: Always wrap streaming calls in try-except blocks and handle provider-specific errors.

3. **Use appropriate timeouts**: Set timeouts based on your use case - shorter for interactive applications, longer for batch processing.

4. **Configure for your needs**: Use preset configurations (JSON_MODE_OPTIONS, etc.) or create custom StreamingOptions.

5. **Monitor performance**: Track streaming metrics to identify bottlenecks and optimize accordingly.

6. **Process incrementally**: For large responses, process chunks as they arrive rather than collecting everything in memory.

7. **Test with different providers**: Each provider has different streaming characteristics - test and tune accordingly.

## Troubleshooting

### Common Issues

**Issue**: Streaming seems slow
```python
# Solution: Optimize streaming options
options = StreamingOptions(
    enable_usage_aggregation=False,  # Disable if not needed
    connection_timeout=3.0,          # Reduce timeout
    retry_on_connection_error=False  # Disable retries
)
```

**Issue**: Missing usage data
```python
# Solution: Ensure you're using stream_with_usage()
response = await client.stream_with_usage(...)  # Not stream()
print(response.usage)  # Will have usage data
```

**Issue**: JSON parsing errors
```python
# Solution: Use JSON_MODE_OPTIONS
from steer_llm_sdk.models.streaming import JSON_MODE_OPTIONS

response = await client.stream_with_usage(
    prompt,
    response_format={"type": "json_object"},
    streaming_options=JSON_MODE_OPTIONS
)
```

For more details on the streaming architecture, see the [Streaming Architecture documentation](../architecture/streaming.md).