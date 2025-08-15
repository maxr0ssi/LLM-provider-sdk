# Streaming Configuration

This guide covers configuration options for streaming operations in the Steer LLM SDK.

## StreamingOptions

The `StreamingOptions` class provides comprehensive control over streaming behavior:

```python
from steer_llm_sdk.models.streaming import StreamingOptions

options = StreamingOptions(
    # Usage tracking
    enable_usage_aggregation=True,
    aggregator_type="auto",  # auto, tiktoken, character
    prefer_tiktoken=True,
    
    # JSON handling
    enable_json_stream_handler=True,
    
    # Event processing
    event_processor=None,  # Custom event processor
    
    # Reliability
    connection_timeout=5.0,
    read_timeout=30.0,
    retry_on_connection_error=True,
    max_reconnect_attempts=3
)
```

## Environment Variables

```bash
# Streaming behavior
export STEER_STREAMING_STATE_TTL=900  # State cleanup after 15 minutes
export STREAMING_CONNECTION_TIMEOUT=5.0
export STREAMING_READ_TIMEOUT=30.0
export STREAMING_MAX_RECONNECTS=3

# Usage aggregation
export STREAMING_ENABLE_AGGREGATION=true
export STREAMING_PREFER_TIKTOKEN=true

# JSON handling
export STREAMING_ENABLE_JSON_HANDLER=true
```

## Preset Configurations

### Built-in Presets

```python
from steer_llm_sdk.models.streaming import (
    JSON_MODE_OPTIONS,
    DEBUG_OPTIONS,
    HIGH_PERFORMANCE_OPTIONS
)

# JSON mode - optimized for structured output
response = await client.stream_with_usage(
    messages="Generate JSON data",
    model="gpt-4",
    response_format={"type": "json_object"},
    streaming_options=JSON_MODE_OPTIONS
)

# Debug mode - detailed tracking
response = await client.stream_with_usage(
    messages="Test prompt",
    model="gpt-4",
    streaming_options=DEBUG_OPTIONS
)

# High performance - minimal overhead
response = await client.stream_with_usage(
    messages="Generate text",
    model="gpt-4",
    streaming_options=HIGH_PERFORMANCE_OPTIONS
)
```

### Custom Presets

```python
# Create custom presets for your use cases
FAST_STREAMING = StreamingOptions(
    enable_usage_aggregation=False,  # Skip token counting
    enable_json_stream_handler=False,  # No JSON parsing
    connection_timeout=3.0,  # Fail fast
    read_timeout=20.0,
    retry_on_connection_error=False  # No retries
)

ACCURATE_USAGE = StreamingOptions(
    enable_usage_aggregation=True,
    prefer_tiktoken=True,  # Accurate token counting
    aggregator_type="tiktoken",
    enable_json_stream_handler=False
)

RELIABLE_STREAMING = StreamingOptions(
    connection_timeout=10.0,
    read_timeout=60.0,
    retry_on_connection_error=True,
    max_reconnect_attempts=5
)
```

## Usage Aggregation

### Aggregator Types

```python
# Automatic selection (recommended)
options = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="auto"  # Chooses based on model
)

# Force specific aggregator
options = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="tiktoken"  # Most accurate
)

# Character-based (fastest)
options = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="character",  # 4:1 approximation
)
```

### Provider-Specific Ratios

```python
# Character to token ratios by provider
CHAR_TO_TOKEN_RATIOS = {
    "openai": 4.0,      # ~4 characters per token
    "anthropic": 3.8,   # Slightly more efficient
    "xai": 4.2,         # Slightly less efficient
    "default": 4.0
}
```

## JSON Streaming

### JSON Handler Configuration

```python
# Enable JSON streaming for structured output
options = StreamingOptions(
    enable_json_stream_handler=True
)

# The handler automatically activates for:
response = await client.stream_with_usage(
    messages="Generate data",
    model="gpt-4",
    response_format={"type": "json_object"},  # Triggers JSON mode
    streaming_options=options
)
```

### JSON Parsing Options

```python
# Custom JSON handling
class CustomJSONProcessor:
    def process_json_object(self, obj):
        # Custom processing logic
        return obj

options = StreamingOptions(
    enable_json_stream_handler=True,
    json_processor=CustomJSONProcessor()  # Future feature
)
```

## Event Processing

### Event Processor Configuration

```python
from steer_llm_sdk.streaming.processor import create_event_processor

# Create processor with options
processor = create_event_processor(
    event_types=["delta", "usage"],  # Filter events
    providers=["openai"],  # Filter by provider
    add_correlation=True,  # Add correlation IDs
    add_timestamp=True,  # Add timestamps
    add_metrics=True,  # Track metrics
    background=True,  # Process in background
    batch_size=50,  # Batch events
    batch_timeout_ms=100  # Batch timeout
)

options = StreamingOptions(
    event_processor=processor
)
```

### Event Callbacks

```python
# Configure callbacks directly
response = await client.stream_with_usage(
    messages="Generate content",
    model="gpt-4",
    on_start=async_start_handler,
    on_delta=async_delta_handler,
    on_usage=async_usage_handler,
    on_complete=async_complete_handler,
    on_error=async_error_handler
)
```

## Performance Tuning

### Low Latency Configuration

```python
# Optimize for minimal latency
LOW_LATENCY = StreamingOptions(
    # Disable expensive features
    enable_usage_aggregation=False,
    enable_json_stream_handler=False,
    
    # Fast timeouts
    connection_timeout=2.0,
    read_timeout=15.0,
    
    # No retries
    retry_on_connection_error=False
)
```

### High Reliability Configuration

```python
# Optimize for reliability
HIGH_RELIABILITY = StreamingOptions(
    # Enable all tracking
    enable_usage_aggregation=True,
    prefer_tiktoken=True,
    
    # Generous timeouts
    connection_timeout=10.0,
    read_timeout=120.0,
    
    # Aggressive retries
    retry_on_connection_error=True,
    max_reconnect_attempts=5
)
```

### Balanced Configuration

```python
# Balanced performance and reliability
BALANCED = StreamingOptions(
    # Moderate features
    enable_usage_aggregation=True,
    prefer_tiktoken=False,  # Use faster approximation
    
    # Reasonable timeouts
    connection_timeout=5.0,
    read_timeout=30.0,
    
    # Limited retries
    retry_on_connection_error=True,
    max_reconnect_attempts=2
)
```

## Memory Management

### State TTL Configuration

```python
import os

# Configure state cleanup
os.environ["STEER_STREAMING_STATE_TTL"] = "600"  # 10 minutes

# Or programmatically
from steer_llm_sdk.reliability import StreamingRetryManager

manager = StreamingRetryManager()
manager._state_ttl_seconds = 600.0

# Manual cleanup for long-running services
cleaned = manager.cleanup_old_states()
print(f"Cleaned up {cleaned} expired states")
```

### Buffer Management

```python
# Control internal buffering (future feature)
options = StreamingOptions(
    buffer_size=100,  # Maximum buffered chunks
    buffer_timeout_ms=100  # Force flush timeout
)
```

## Provider-Specific Settings

### OpenAI Streaming

```python
# OpenAI-specific optimizations
OPENAI_STREAMING = StreamingOptions(
    enable_usage_aggregation=True,
    prefer_tiktoken=True,  # Native token counting
    connection_timeout=5.0,
    read_timeout=30.0
)
```

### Anthropic Streaming

```python
# Anthropic-specific settings
ANTHROPIC_STREAMING = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="character",  # No tiktoken support
    connection_timeout=5.0,
    read_timeout=60.0  # Anthropic can be slower
)
```

### xAI Streaming

```python
# xAI-specific configuration
XAI_STREAMING = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="character",
    connection_timeout=10.0,  # xAI may need more time
    read_timeout=45.0
)
```

## Monitoring Configuration

### Streaming Metrics

```python
# Enable detailed streaming metrics
options = StreamingOptions(
    enable_usage_aggregation=True,
    track_metrics=True  # Future feature
)

# Access metrics after streaming
response = await client.stream_with_usage(
    messages="Test",
    model="gpt-4",
    streaming_options=options
)

print(f"Chunks received: {response.metrics['chunks']}")
print(f"Chars/second: {response.metrics['chars_per_second']}")
print(f"Time to first token: {response.metrics['time_to_first_token_ms']}ms")
```

## Advanced Configurations

### Conditional Configuration

```python
def get_streaming_options(model: str, response_format: dict = None) -> StreamingOptions:
    """Get optimal streaming options based on context."""
    
    # Base options
    options = StreamingOptions()
    
    # JSON mode
    if response_format and response_format.get("type") == "json_object":
        options.enable_json_stream_handler = True
        options.enable_usage_aggregation = True
    
    # Model-specific
    if model.startswith("gpt"):
        options.prefer_tiktoken = True
    elif model.startswith("claude"):
        options.read_timeout = 60.0  # Claude can be slower
    elif model.startswith("grok"):
        options.connection_timeout = 10.0  # xAI needs more time
    
    return options
```

### Dynamic Configuration

```python
class AdaptiveStreamingOptions:
    """Streaming options that adapt based on conditions."""
    
    def __init__(self):
        self.base_options = StreamingOptions()
        self.network_quality = "good"  # good, fair, poor
    
    def get_options(self) -> StreamingOptions:
        """Get options based on current conditions."""
        options = StreamingOptions()
        
        if self.network_quality == "poor":
            # More aggressive retries, longer timeouts
            options.connection_timeout = 10.0
            options.read_timeout = 60.0
            options.max_reconnect_attempts = 5
        elif self.network_quality == "fair":
            # Balanced settings
            options.connection_timeout = 5.0
            options.read_timeout = 30.0
            options.max_reconnect_attempts = 3
        else:  # good
            # Optimized for speed
            options.connection_timeout = 3.0
            options.read_timeout = 20.0
            options.max_reconnect_attempts = 1
        
        return options
```

## Best Practices

1. **Start with presets** - Use JSON_MODE, DEBUG, or HIGH_PERFORMANCE
2. **Enable aggregation selectively** - Only when you need usage data
3. **Match timeouts to use case** - Short for UI, long for batch
4. **Configure retries appropriately** - More for critical, less for interactive
5. **Use tiktoken sparingly** - Only when accuracy is critical
6. **Disable unused features** - Every feature has overhead
7. **Monitor performance** - Track latency and throughput
8. **Test configurations** - Different models behave differently
9. **Document custom settings** - For team consistency
10. **Review periodically** - Optimal settings change over time