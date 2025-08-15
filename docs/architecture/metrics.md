# Metrics Architecture

## Overview

The Steer LLM SDK includes a comprehensive metrics collection system designed to provide observability into LLM operations. The system is lightweight, extensible, and integrates seamlessly with popular monitoring tools.

## Architecture Components

### 1. Metrics Models (`observability/models.py`)

The SDK defines several metric types to capture different aspects of LLM operations:

- **RequestMetrics**: Core request-level metrics (latency, tokens, errors)
- **StreamingMetrics**: Streaming-specific metrics (chunks, throughput, TTFT)
- **ReliabilityMetrics**: Retry and circuit breaker metrics
- **UsageMetrics**: Aggregated usage over time windows
- **ErrorMetrics**: Detailed error tracking

```python
@dataclass
class RequestMetrics(BaseMetrics):
    duration_ms: float
    time_to_first_token_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int
    method: str  # generate, stream
    response_format: str  # text, json_object
```

### 2. Metrics Collector (`observability/collector.py`)

The central component that:
- Manages metric collection lifecycle
- Supports batching for performance
- Implements sampling and filtering
- Dispatches metrics to multiple sinks

```python
# Basic usage
from steer_llm_sdk.observability import MetricsCollector, MetricsConfig

collector = MetricsCollector(
    config=MetricsConfig(
        enabled=True,
        batch_size=100,
        request_sampling_rate=1.0
    )
)

# Track a request
async with collector.track_request(
    provider="openai",
    model="gpt-4",
    method="generate"
) as metrics:
    # Your LLM operation
    response = await llm.generate(...)
    
    # Update metrics
    metrics.prompt_tokens = response.usage.prompt_tokens
    metrics.completion_tokens = response.usage.completion_tokens
```

### 3. Metrics Sinks

Sinks are pluggable destinations for metrics:

#### In-Memory Sink (`sinks/in_memory.py`)
- Stores metrics in memory with circular buffer
- Provides query and aggregation capabilities
- Useful for testing and debugging

```python
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink

sink = InMemoryMetricsSink(max_size=10000, ttl_seconds=3600)
collector.add_sink(sink)

# Query metrics
metrics = await sink.get_metrics(
    start_time=time.time() - 300,  # Last 5 minutes
    provider="openai"
)

# Get summary statistics
summary = await sink.get_summary(window_seconds=300)
print(f"Avg latency: {summary.avg_latency_ms}ms")
print(f"P95 latency: {summary.p95_latency_ms}ms")
```

#### OTLP Sink (`sinks/otlp.py`)
- Exports metrics via OpenTelemetry Protocol
- Compatible with Prometheus, Jaeger, etc.
- Supports custom attributes and namespaces

```python
from steer_llm_sdk.observability.sinks import OTelMetricsSink

sink = OTelMetricsSink(
    service_name="my-llm-service",
    namespace="llm"
)
collector.add_sink(sink)
```

#### Custom Sinks
Implement the `MetricsSink` protocol:

```python
from steer_llm_sdk.observability.sinks import MetricsSink

class CustomMetricsSink(MetricsSink):
    async def record(self, metrics: AgentMetrics) -> None:
        # Send to your backend
        await my_backend.send(metrics)
    
    async def flush(self) -> None:
        # Flush any buffered data
        await my_backend.flush()
```

## Integration Points

### 1. Client Integration

The `SteerLLMClient` automatically tracks metrics:

```python
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.observability import MetricsConfig
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink

client = SteerLLMClient(
    metrics_config=MetricsConfig(enabled=True),
    metrics_sinks=[InMemoryMetricsSink()]
)

# Metrics are automatically collected
response = await client.generate("Hello!", model="gpt-4")
```

### 2. Streaming Integration

Streaming operations track additional metrics:

```python
response = await client.stream_with_usage(
    messages="Write a story",
    model="gpt-4"
)

# Metrics include:
# - Time to first token (TTFT)
# - Chunks per second
# - Total streaming duration
# - JSON parsing statistics (if applicable)
```

### 3. Reliability Integration

The reliability layer reports retry and circuit breaker metrics:

```python
# Automatically tracked:
# - Retry attempts and success rate
# - Circuit breaker state changes
# - Error categories and retry delays
```

## Performance Considerations

### 1. Overhead

The metrics system is designed for minimal overhead:
- Async collection (non-blocking)
- Batching reduces I/O operations
- Sampling controls data volume
- Typical overhead: < 1% of request time

### 2. Memory Usage

- In-memory sink uses circular buffer (configurable size)
- Metrics are lightweight data classes
- Old metrics are automatically pruned

### 3. Configuration

```python
config = MetricsConfig(
    enabled=True,  # Global enable/disable
    batch_size=100,  # Batch metrics before sending
    batch_timeout_seconds=1.0,  # Max time before flush
    
    # Feature flags
    enable_streaming_metrics=True,
    enable_reliability_metrics=True,
    enable_cost_tracking=False,
    
    # Sampling (0.0 to 1.0)
    request_sampling_rate=1.0,
    streaming_sampling_rate=0.5,
    error_sampling_rate=1.0,
    
    # Filters
    filters=[OnlyProductionFilter()]
)
```

## Metrics Reference

### Request Metrics

| Metric | Type | Description |
|--------|------|-------------|
| duration_ms | float | Total request duration |
| time_to_first_token_ms | float | Time to first streaming token |
| prompt_tokens | int | Input token count |
| completion_tokens | int | Output token count |
| cached_tokens | int | Cached prompt tokens |
| provider | string | LLM provider name |
| model | string | Model identifier |
| method | string | generate or stream |
| error_class | string | Error type if failed |

### Streaming Metrics

| Metric | Type | Description |
|--------|------|-------------|
| total_chunks | int | Number of chunks received |
| total_chars | int | Total characters streamed |
| chunks_per_second | float | Streaming throughput |
| first_chunk_latency_ms | float | Time to first chunk |
| json_objects_found | int | JSON objects parsed |
| aggregation_method | string | Token counting method |
| aggregation_confidence | float | Accuracy confidence (0-1) |

### Reliability Metrics

| Metric | Type | Description |
|--------|------|-------------|
| retry_attempts | int | Number of retry attempts |
| retry_succeeded | bool | Whether retry succeeded |
| total_retry_delay_ms | float | Total time spent retrying |
| circuit_breaker_state | string | CLOSED, OPEN, HALF_OPEN |
| error_category | string | Error classification |

## Example: Production Setup

```python
import os
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.observability import MetricsConfig, MetricsCollector
from steer_llm_sdk.observability.sinks import OTelMetricsSink, InMemoryMetricsSink

# Configure metrics
config = MetricsConfig(
    enabled=True,
    batch_size=100,
    request_sampling_rate=float(os.getenv("METRICS_SAMPLING_RATE", "1.0")),
    enable_cost_tracking=os.getenv("ENABLE_COST_TRACKING") == "true"
)

# Create collector with multiple sinks
collector = MetricsCollector(config)

# OTLP for production monitoring
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    collector.add_sink(OTelMetricsSink(
        service_name=os.getenv("SERVICE_NAME", "llm-service"),
        namespace="production"
    ))

# In-memory for debugging
if os.getenv("DEBUG_METRICS") == "true":
    debug_sink = InMemoryMetricsSink()
    collector.add_sink(debug_sink)
    
    # Expose debug endpoint
    @app.get("/metrics/debug")
    async def debug_metrics():
        return await debug_sink.get_summary()

# Create client with metrics
client = SteerLLMClient(metrics_collector=collector)

# Use client normally - metrics are automatic
response = await client.generate(
    messages="Explain quantum computing",
    model="gpt-4"
)
```

## Best Practices

1. **Enable in Production**: Always enable metrics in production for observability
2. **Use Sampling**: For high-volume services, use sampling to control costs
3. **Multiple Sinks**: Use OTLP for monitoring and in-memory for debugging
4. **Custom Attributes**: Add service-specific attributes via filters
5. **Alert on Metrics**: Set up alerts for error rates, latency spikes, etc.
6. **Cost Tracking**: Enable cost tracking to monitor LLM expenses
7. **Batch Configuration**: Tune batch size based on traffic volume

## Troubleshooting

### Metrics Not Appearing

1. Check that metrics are enabled: `config.enabled = True`
2. Verify sink is added: `collector.add_sink(sink)`
3. Check sampling rate: `config.request_sampling_rate > 0`
4. Ensure async operations complete: `await collector.flush()`

### High Memory Usage

1. Reduce in-memory sink size: `InMemoryMetricsSink(max_size=1000)`
2. Decrease TTL: `InMemoryMetricsSink(ttl_seconds=300)`
3. Use sampling: `config.request_sampling_rate = 0.1`
4. Enable batching: `config.batch_size = 100`

### Performance Impact

1. Disable unnecessary features:
   ```python
   config.enable_streaming_metrics = False
   config.enable_cost_tracking = False
   ```
2. Increase batch size: `config.batch_size = 500`
3. Use sampling for high-volume endpoints
4. Use async sinks to avoid blocking