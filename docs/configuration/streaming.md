# Streaming Configuration

Configuration options for streaming operations.

## StreamingOptions

```python
from steer_llm_sdk.models.streaming import StreamingOptions

options = StreamingOptions(
    # Usage tracking
    enable_usage_aggregation=True,
    aggregator_type="auto",  # auto, tiktoken, character
    prefer_tiktoken=True,

    # JSON handling
    enable_json_stream_handler=True,

    # Reliability
    connection_timeout=5.0,
    read_timeout=30.0,
    retry_on_connection_error=True,
    max_reconnect_attempts=3
)

response = await client.stream_with_usage(
    "Generate data",
    model="gpt-4",
    streaming_options=options
)
```

## Environment Variables

```bash
export STEER_STREAMING_STATE_TTL=900  # State cleanup (seconds)
export STREAMING_CONNECTION_TIMEOUT=5.0
export STREAMING_READ_TIMEOUT=30.0
export STREAMING_MAX_RECONNECTS=3
export STREAMING_ENABLE_AGGREGATION=true
export STREAMING_PREFER_TIKTOKEN=true
export STREAMING_ENABLE_JSON_HANDLER=true
```

## Presets

```python
from steer_llm_sdk.models.streaming import (
    JSON_MODE_OPTIONS,
    HIGH_THROUGHPUT_OPTIONS,
    LOW_LATENCY_OPTIONS
)

# JSON mode - optimized for structured output
response = await client.stream_with_usage(
    "Generate JSON",
    model="gpt-4",
    response_format={"type": "json_object"},
    streaming_options=JSON_MODE_OPTIONS
)

# High throughput - maximum performance
response = await client.stream_with_usage(
    "Generate text",
    model="gpt-4",
    streaming_options=HIGH_THROUGHPUT_OPTIONS
)

# Low latency - minimal overhead
response = await client.stream_with_usage(
    "Quick response",
    model="gpt-4",
    streaming_options=LOW_LATENCY_OPTIONS
)
```

## Usage Aggregation

```python
# Automatic (recommended)
options = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="auto"  # Chooses based on model
)

# Tiktoken (most accurate, slower)
options = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="tiktoken"
)

# Character-based (fast approximation)
options = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="character"  # ~4:1 ratio
)
```

## Event Callbacks

```python
async def on_start():
    print("Stream started")

async def on_delta(text: str):
    print(f"Delta: {text}")

async def on_complete(final_text: str):
    print("Complete")

response = await client.stream_with_usage(
    "Generate",
    model="gpt-4",
    streaming_options=StreamingOptions(
        on_start=on_start,
        on_delta=on_delta,
        on_complete=on_complete
    )
)
```

## Performance Tuning

### Low Latency

```python
LOW_LATENCY = StreamingOptions(
    enable_usage_aggregation=False,
    enable_json_stream_handler=False,
    connection_timeout=2.0,
    read_timeout=15.0,
    retry_on_connection_error=False
)
```

### High Reliability

```python
HIGH_RELIABILITY = StreamingOptions(
    enable_usage_aggregation=True,
    prefer_tiktoken=True,
    connection_timeout=10.0,
    read_timeout=120.0,
    retry_on_connection_error=True,
    max_reconnect_attempts=5
)
```

## Provider-Specific

### OpenAI

```python
OPENAI_STREAMING = StreamingOptions(
    enable_usage_aggregation=True,
    prefer_tiktoken=True,
    connection_timeout=5.0,
    read_timeout=30.0
)
```

### Anthropic

```python
ANTHROPIC_STREAMING = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="character",  # No tiktoken support
    connection_timeout=5.0,
    read_timeout=60.0
)
```

### xAI

```python
XAI_STREAMING = StreamingOptions(
    enable_usage_aggregation=True,
    aggregator_type="character",
    connection_timeout=10.0,
    read_timeout=45.0
)
```

## Best Practices

1. Start with presets (JSON_MODE, HIGH_THROUGHPUT, LOW_LATENCY)
2. Enable aggregation only when you need usage data
3. Match timeouts to your use case (short for UI, long for batch)
4. Use tiktoken only when accuracy is critical
5. Disable unused features to reduce overhead
6. Test configurations with your specific models
