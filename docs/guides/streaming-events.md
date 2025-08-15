# Streaming Events Guide

This guide explains how to use the streaming events system in the Steer LLM SDK to monitor and react to events during text generation.

## Overview

The streaming events system provides real-time visibility into the streaming process through typed events. This enables:

- Progress tracking and monitoring
- Error handling and recovery
- Metrics collection and analysis
- Custom processing pipelines
- Debugging and troubleshooting

## Event Types

The SDK emits five types of events during streaming:

### StreamStartEvent
Emitted when streaming begins.
```python
@dataclass
class StreamStartEvent:
    provider: str          # Provider name (e.g., "openai")
    model: str            # Model name (e.g., "gpt-4")
    request_id: str       # Unique request identifier
    stream_id: str        # Stream session ID
    timestamp: float      # Unix timestamp
    metadata: Dict        # Additional metadata
```

### StreamDeltaEvent
Emitted for each text chunk received.
```python
@dataclass
class StreamDeltaEvent:
    delta: Union[str, Dict]  # Text chunk or structured data
    chunk_index: int         # Sequential chunk number
    is_json: bool           # Whether this is JSON data
    provider: str           # Provider name
    model: str              # Model name
    # ... inherited fields
```

### StreamUsageEvent
Emitted when token usage data is available.
```python
@dataclass
class StreamUsageEvent:
    usage: Dict[str, Any]    # Token usage data
    is_estimated: bool       # Whether usage is estimated
    confidence: float        # Confidence score (0-1)
    # ... inherited fields
```

### StreamCompleteEvent
Emitted when streaming completes successfully.
```python
@dataclass
class StreamCompleteEvent:
    total_chunks: int        # Total chunks received
    duration_ms: float       # Total streaming duration
    final_usage: Dict        # Final usage data
    # ... inherited fields
```

### StreamErrorEvent
Emitted when an error occurs.
```python
@dataclass
class StreamErrorEvent:
    error: Exception         # The error that occurred
    error_type: str         # Error class name
    is_retryable: bool      # Whether retry is possible
    # ... inherited fields
```

## Using Event Callbacks

### Basic Usage

The simplest way to use events is through callbacks in the client API:

```python
import asyncio
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.models.events import *

client = SteerLLMClient()

# Define event callbacks
async def on_start(event: StreamStartEvent):
    print(f"Streaming started: {event.provider}/{event.model}")
    print(f"Request ID: {event.request_id}")

async def on_delta(event: StreamDeltaEvent):
    text = event.get_text()
    print(f"Chunk {event.chunk_index}: {text}")

async def on_usage(event: StreamUsageEvent):
    usage = event.usage
    print(f"Tokens - Prompt: {usage.get('prompt_tokens')}, "
          f"Completion: {usage.get('completion_tokens')}")
    if event.is_estimated:
        print(f"(Estimated with {event.confidence:.0%} confidence)")

async def on_complete(event: StreamCompleteEvent):
    print(f"Completed! {event.total_chunks} chunks in {event.duration_ms:.0f}ms")

async def on_error(event: StreamErrorEvent):
    print(f"Error: {event.error_type} - {event.error}")
    if event.is_retryable:
        print("This error is retryable")

# Stream with callbacks
response = await client.stream_with_usage(
    messages="Write a short poem about AI",
    model="gpt-4",
    on_start=on_start,
    on_delta=on_delta,
    on_usage=on_usage,
    on_complete=on_complete,
    on_error=on_error
)

print(f"Full response: {response.get_text()}")
```

### Selective Event Handling

You can subscribe to only the events you're interested in:

```python
# Only track start and completion
response = await client.stream_with_usage(
    messages="Hello, world!",
    model="gpt-4",
    on_start=lambda e: print(f"Started at {e.timestamp}"),
    on_complete=lambda e: print(f"Done in {e.duration_ms}ms")
)
```

## Advanced Event Processing

### Using Event Processors

For more complex scenarios, use the event processor pipeline:

```python
from steer_llm_sdk.streaming.processor import create_event_processor
from steer_llm_sdk.models.streaming import StreamingOptions

# Create a processor with filters and transformers
processor = create_event_processor(
    event_types=[StreamDeltaEvent, StreamUsageEvent],  # Only these types
    providers=["openai"],                               # Only OpenAI
    add_correlation=True,                               # Add correlation IDs
    add_timestamp=True,                                 # Add timestamps
    add_metrics=True                                    # Track metrics
)

# Use with streaming options
options = StreamingOptions(event_processor=processor)

response = await client.stream_with_usage(
    messages="Test",
    model="gpt-4",
    streaming_options=options
)
```

### Custom Event Filters

Create custom filters for fine-grained control:

```python
from steer_llm_sdk.streaming.processor import EventProcessor, PredicateFilter

# Filter for long chunks only
long_chunk_filter = PredicateFilter(
    lambda event: (
        isinstance(event, StreamDeltaEvent) and 
        len(event.get_text()) > 50
    )
)

processor = EventProcessor(filters=[long_chunk_filter])
```

### Event Transformation

Transform events to add custom data:

```python
from steer_llm_sdk.streaming.processor import EventTransformer

class CustomTransformer(EventTransformer):
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    async def transform(self, event):
        # Add user context to all events
        event.metadata['user_id'] = self.user_id
        event.metadata['app_version'] = '1.0.0'
        return event

processor = EventProcessor()
processor.add_transformer(CustomTransformer(user_id="user123"))
```

### Batched Event Processing

For high-volume streaming, batch events for efficient processing:

```python
from steer_llm_sdk.streaming.processor import create_event_processor

async def handle_batch(events: List[StreamEvent]):
    # Process batch of events
    print(f"Processing {len(events)} events")
    # Send to analytics, database, etc.

processor = create_event_processor(
    batch_size=100,              # Batch up to 100 events
    batch_timeout_ms=500,        # Or every 500ms
    batch_handler=handle_batch
)
```

## Metrics and Monitoring

### Time to First Token (TTFT)

Track how quickly the first token arrives:

```python
start_time = None
ttft = None

async def on_start(event: StreamStartEvent):
    global start_time
    start_time = event.timestamp

async def on_delta(event: StreamDeltaEvent):
    global ttft
    if ttft is None and event.chunk_index == 0:
        ttft = (event.timestamp - start_time) * 1000
        print(f"Time to first token: {ttft:.0f}ms")
```

### Streaming Throughput

Monitor tokens per second:

```python
async def on_complete(event: StreamCompleteEvent):
    if event.final_usage:
        tokens = event.final_usage.get('completion_tokens', 0)
        duration_sec = event.duration_ms / 1000
        throughput = tokens / duration_sec if duration_sec > 0 else 0
        print(f"Throughput: {throughput:.1f} tokens/second")
```

### Usage Tracking

Track token usage across providers:

```python
usage_by_provider = {}

async def on_usage(event: StreamUsageEvent):
    provider = event.provider
    if provider not in usage_by_provider:
        usage_by_provider[provider] = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'requests': 0
        }
    
    usage = event.usage
    usage_by_provider[provider]['prompt_tokens'] += usage.get('prompt_tokens', 0)
    usage_by_provider[provider]['completion_tokens'] += usage.get('completion_tokens', 0)
    usage_by_provider[provider]['requests'] += 1
```

## Error Handling

### Retry Logic

Implement retry logic based on error types:

```python
async def handle_with_retry(messages, model, max_retries=3):
    for attempt in range(max_retries):
        try:
            error_event = None
            
            async def on_error(event: StreamErrorEvent):
                nonlocal error_event
                error_event = event
            
            response = await client.stream_with_usage(
                messages=messages,
                model=model,
                on_error=on_error
            )
            
            if error_event and error_event.is_retryable:
                print(f"Retryable error on attempt {attempt + 1}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            
            return response
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"Error on attempt {attempt + 1}: {e}")
```

## JSON Streaming

Handle JSON responses with proper validation:

```python
async def on_delta(event: StreamDeltaEvent):
    if event.is_json:
        # This is part of a JSON response
        print(f"JSON chunk: {event.get_text()}")

response = await client.stream_with_usage(
    messages="Return a JSON object with name and age",
    model="gpt-4",
    response_format={"type": "json_object"},
    on_delta=on_delta
)

# The SDK handles JSON assembly and validation
import json
data = json.loads(response.get_text())
print(f"Parsed JSON: {data}")
```

## Performance Considerations

### Event Processing Overhead

- Event processing adds < 1ms overhead per event
- Use batching for high-volume streams
- Disable unused features in production

### Memory Usage

- Events are processed in-place (no buffering)
- Batch processors buffer up to batch_size events
- Use streaming for large responses to minimize memory

### Best Practices

1. **Filter Early**: Use type and provider filters to reduce processing
2. **Async Callbacks**: Keep callbacks lightweight and async
3. **Error Handling**: Always provide an error callback
4. **Correlation**: Use correlation IDs for request tracing
5. **Metrics**: Track key metrics but avoid over-instrumentation

## Complete Examples

### Analytics Integration

```python
from datetime import datetime
import json

class AnalyticsCollector:
    def __init__(self):
        self.sessions = []
        self.current_session = None
    
    async def on_start(self, event: StreamStartEvent):
        self.current_session = {
            'id': event.request_id,
            'provider': event.provider,
            'model': event.model,
            'start_time': datetime.utcnow().isoformat(),
            'chunks': [],
            'errors': []
        }
    
    async def on_delta(self, event: StreamDeltaEvent):
        if self.current_session:
            self.current_session['chunks'].append({
                'index': event.chunk_index,
                'size': len(event.get_text()),
                'timestamp': event.timestamp
            })
    
    async def on_error(self, event: StreamErrorEvent):
        if self.current_session:
            self.current_session['errors'].append({
                'type': event.error_type,
                'message': str(event.error),
                'retryable': event.is_retryable
            })
    
    async def on_complete(self, event: StreamCompleteEvent):
        if self.current_session:
            self.current_session['end_time'] = datetime.utcnow().isoformat()
            self.current_session['total_chunks'] = event.total_chunks
            self.current_session['duration_ms'] = event.duration_ms
            self.current_session['usage'] = event.final_usage
            
            # Send to analytics service
            await self.send_to_analytics(self.current_session)
            self.sessions.append(self.current_session)
            self.current_session = None
    
    async def send_to_analytics(self, session_data):
        # Implement your analytics integration
        print(f"Analytics: {json.dumps(session_data, indent=2)}")

# Use the collector
collector = AnalyticsCollector()

response = await client.stream_with_usage(
    messages="Analyze this text",
    model="gpt-4",
    on_start=collector.on_start,
    on_delta=collector.on_delta,
    on_error=collector.on_error,
    on_complete=collector.on_complete
)
```

### Progress Indicator

```python
import sys

class ProgressTracker:
    def __init__(self):
        self.chunks_received = 0
        self.start_time = None
    
    async def on_start(self, event: StreamStartEvent):
        self.start_time = event.timestamp
        print("Streaming: ", end='', flush=True)
    
    async def on_delta(self, event: StreamDeltaEvent):
        self.chunks_received += 1
        # Show progress dots
        if self.chunks_received % 10 == 0:
            print(".", end='', flush=True)
    
    async def on_complete(self, event: StreamCompleteEvent):
        elapsed = event.timestamp - self.start_time
        print(f"\nCompleted! {self.chunks_received} chunks in {elapsed:.1f}s")

tracker = ProgressTracker()

response = await client.stream_with_usage(
    messages="Write a story",
    model="gpt-4",
    on_start=tracker.on_start,
    on_delta=tracker.on_delta,
    on_complete=tracker.on_complete
)
```

## Migration Guide

If you're upgrading from an older version without typed events:

### Before (Untyped)
```python
async def on_delta(data):
    if isinstance(data, dict) and 'text' in data:
        print(data['text'])
```

### After (Typed)
```python
async def on_delta(event: StreamDeltaEvent):
    print(event.get_text())
```

The new system is backward compatible - old callbacks still work, but we recommend migrating to typed events for better type safety and IDE support.

## Troubleshooting

### Events Not Firing

1. Check that callbacks are async functions
2. Ensure streaming_options are passed correctly
3. Verify the provider supports event emission

### Performance Issues

1. Reduce event processing overhead by filtering
2. Use batching for high-volume streams
3. Disable unnecessary transformers

### Memory Leaks

1. Avoid storing events in callbacks
2. Clear references in on_complete/on_error
3. Use weak references for long-lived collectors

## API Reference

See the API documentation for detailed information on:
- [`StreamEvent`](../api/events.md#streamevent) - Base event class
- [`EventProcessor`](../api/processor.md#eventprocessor) - Event processing pipeline
- [`EventManager`](../api/manager.md#eventmanager) - Event callback manager
- [`StreamingOptions`](../api/streaming.md#streamingoptions) - Configuration options