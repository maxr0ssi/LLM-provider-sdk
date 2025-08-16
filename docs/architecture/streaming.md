# Streaming Architecture

## Overview

The Steer LLM SDK uses a unified streaming architecture that provides consistent behavior across all providers while maintaining flexibility for provider-specific features. The architecture is built around three core components that work together to handle streaming responses.

## Architecture Components

### 1. StreamingHelper (Orchestration Layer)

The `StreamingHelper` class provides high-level streaming patterns that orchestrate the entire streaming flow:

```python
# Collect all chunks with usage data
text, usage, metrics = await StreamingHelper.collect_with_usage(
    stream, adapter, events
)

# Stream chunks while emitting events
async for chunk in StreamingHelper.stream_with_events(
    stream, adapter, events
):
    print(chunk)
```

**Key responsibilities:**
- Handles tuple format `(chunk, usage_data)` from providers
- Manages chunk collection and aggregation
- Coordinates event emission
- Tracks streaming metrics
- Ensures proper adapter lifecycle (start/complete)

### 2. EventProcessor (Pipeline Layer)

The `EventProcessor` provides a composable pipeline for filtering, transforming, and processing streaming events:

```python
# Create processor with transformers
processor = create_event_processor(
    add_correlation=True,      # Add correlation IDs
    add_timestamp=True,        # Add timestamps
    add_metrics=True,          # Track metrics
    background=False           # Process synchronously
)

# Attach to adapter
adapter.set_event_processor(processor)
```

**Key features:**
- **Filters**: Type-based, provider-based, custom predicates
- **Transformers**: Correlation IDs, timestamps, metrics extraction
- **Batching**: Efficient batch processing with timeout
- **Background processing**: Optional async processing

### 3. StreamAdapter (Provider Normalization Layer)

The `StreamAdapter` normalizes provider-specific events into a consistent format:

```python
adapter = StreamAdapter("openai")
adapter.model = "gpt-4"
adapter.response_format = {"type": "json_object"}  # JSON mode

# Adapter handles:
# - Delta normalization
# - JSON reconstruction
# - Usage aggregation
# - Lifecycle events
```

**Key features:**
- Provider-specific delta normalization
- JSON mode support with automatic reconstruction
- Usage data aggregation
- Event emission through attached processor
- Streaming metrics collection

## Event Flow

```
Provider Stream → StreamingHelper → StreamAdapter → EventProcessor → Event Callbacks
                       ↓                  ↓              ↓
                  Orchestration    Normalization    Pipeline
                  (collect/stream)  (delta/usage)   (filter/transform)
```

## Integration Points

### 1. AgentRunner Integration

```python
# Configure adapter
adapter = StreamAdapter(provider_name)
adapter.model = definition.model

# Create event manager for callbacks
events = EventManager(
    on_start=opts.metadata.get("on_start"),
    on_delta=opts.metadata.get("on_delta"),
    on_usage=opts.metadata.get("on_usage"),
    on_complete=opts.metadata.get("on_complete"),
    on_error=opts.metadata.get("on_error")
)

# Use StreamingHelper
text, usage_data, metrics = await StreamingHelper.collect_with_usage(
    stream, adapter, events
)
```

### 2. API Client Integration

```python
# Create adapter with event processor
adapter = StreamAdapter(provider)
adapter.set_event_processor(create_event_processor(
    add_correlation=True,
    add_timestamp=True
))

# Stream with callbacks
text, usage, metrics = await StreamingHelper.collect_with_usage(
    self.router.generate_stream(messages, model, params, True),
    adapter,
    events  # Optional EventManager for callbacks
)
```

### 3. Provider Adapter Integration

Provider adapters emit raw chunks that are processed through the streaming pipeline:

```python
# In provider adapter
async for chunk in provider_stream:
    # Yield raw chunk or tuple format
    if has_usage:
        yield (chunk, {"usage": usage_data})
    else:
        yield chunk
```

## Streaming Events

The architecture supports typed streaming events with rich metadata:

### Event Types

1. **StreamStartEvent**: Emitted when streaming begins
   - Contains: provider, model, request metadata

2. **StreamDeltaEvent**: Emitted for each text chunk
   - Contains: delta content, chunk index, is_json flag

3. **StreamUsageEvent**: Emitted when usage data is available
   - Contains: token counts, cost estimates, confidence

4. **StreamCompleteEvent**: Emitted when streaming ends successfully
   - Contains: total chunks, duration, final usage

5. **StreamErrorEvent**: Emitted on streaming errors
   - Contains: error type, is_retryable flag, error details

### Event Metadata

All events include standard metadata:
- `timestamp`: Event timestamp
- `sdk_version`: SDK version
- `correlation_id`: Request correlation ID (if enabled)
- Provider and model information

## JSON Mode Support

The architecture includes built-in support for JSON streaming:

```python
# Enable JSON mode
adapter.response_format = {"type": "json_object"}

# StreamingHelper automatically:
# - Tracks partial JSON in buffer
# - Reconstructs complete JSON objects
# - Sets is_json flag on delta events
# - Returns final JSON in response
```

## Usage Aggregation

Usage data can come from multiple sources and is intelligently aggregated:

1. **Provider Usage**: Direct from provider in tuple format
2. **Aggregated Usage**: Token counting across chunks
3. **Estimated Usage**: Fallback estimation if needed

The architecture ensures only one usage event is emitted per stream.

## Metrics Collection

Streaming metrics are automatically collected:

```python
metrics = {
    "chunks": 10,                    # Total chunks
    "total_chars": 523,             # Total characters
    "duration_seconds": 2.3,        # Stream duration
    "chunks_per_second": 4.3,       # Throughput
    "chars_per_second": 227.4       # Character rate
}
```

## Error Handling

Errors are properly classified and propagated:

```python
# Adapter uses ErrorMapper for classification
is_retryable = ErrorMapper.is_retryable(error)

# Error events include retryability
await events.emit_error(events.create_error_event(
    error=e,
    error_type=type(e).__name__,
    is_retryable=is_retryable
))
```

## Best Practices

1. **Always use StreamingHelper** for consistency
2. **Configure StreamAdapter** with model and response format
3. **Attach EventProcessor** for pipeline features
4. **Use EventManager** for backward-compatible callbacks
5. **Handle errors** with proper classification
6. **Track metrics** for performance monitoring

## Migration Guide

### From Manual Streaming Loops

Before:
```python
async for item in stream:
    if isinstance(item, tuple):
        chunk, usage = item
        # Manual processing...
    else:
        # Manual processing...
```

After:
```python
text, usage, metrics = await StreamingHelper.collect_with_usage(
    stream, adapter, events
)
```

### From Direct Event Emission

Before:
```python
await events.emit_delta({"text": chunk})
await events.emit_usage(usage)
```

After:
```python
# StreamingHelper handles all event emission
# Just pass the EventManager to collect_with_usage
```

## Testing

The streaming architecture includes comprehensive tests:

- Event flow validation
- JSON mode handling
- Error propagation
- Metrics collection
- Adapter lifecycle
- Backward compatibility

See `tests/integration/test_streaming_consolidation.py` for examples.