# Metrics Architecture

Overview of the metrics collection system for LLM observability.

## Components

### 1. Metrics Models

Core metric types:
- **RequestMetrics** - Latency, tokens, cost, errors
- **StreamingMetrics** - Chunks, throughput, time to first token
- **ReliabilityMetrics** - Retries, circuit breaker trips
- **UsageMetrics** - Aggregated usage over time

```python
@dataclass
class RequestMetrics:
    duration_ms: float
    time_to_first_token_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int
    method: str  # generate, stream
    response_format: str  # text, json_object
```

### 2. Metrics Collector

Central component that manages metric collection lifecycle:

```python
from steer_llm_sdk.observability import MetricsCollector, MetricsConfig

collector = MetricsCollector(
    config=MetricsConfig(
        enabled=True,
        batch_size=100,
        request_sampling_rate=1.0
    )
)

# Track request
async with collector.track_request(
    provider="openai",
    model="gpt-4",
    method="generate"
) as metrics:
    response = await llm.generate(...)
    metrics.prompt_tokens = response.usage.prompt_tokens
    metrics.completion_tokens = response.usage.completion_tokens
```

### 3. Metrics Sinks

Pluggable destinations for metrics:

#### In-Memory Sink

```python
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink

sink = InMemoryMetricsSink(max_size=10000, ttl_seconds=3600)
collector.add_sink(sink)

# Query metrics
metrics = await sink.get_metrics(
    start_time=time.time() - 300,
    provider="openai"
)

# Summary statistics
summary = await sink.get_summary(window_seconds=300)
print(f"Avg latency: {summary.avg_latency_ms}ms")
```

#### OTLP Sink

```python
from steer_llm_sdk.observability.sinks import OTelMetricsSink

sink = OTelMetricsSink(
    service_name="my-llm-service",
    namespace="llm"
)
collector.add_sink(sink)
```

#### Custom Sinks

```python
from steer_llm_sdk.observability.sinks import MetricsSink

class CustomMetricsSink(MetricsSink):
    async def record(self, metrics: AgentMetrics) -> None:
        await my_backend.send(metrics)

    async def flush(self) -> None:
        await my_backend.flush()
```

## Integration

### Client Integration

```python
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink

client = SteerLLMClient(
    metrics_config=MetricsConfig(enabled=True),
    metrics_sinks=[InMemoryMetricsSink()]
)

# Metrics automatically collected
response = await client.generate("Hello!", model="gpt-4")
```

### Streaming Integration

```python
response = await client.stream_with_usage(
    "Write a story",
    model="gpt-4"
)

# Streaming metrics include:
# - time_to_first_token_ms
# - chunks_per_second
# - throughput_chars_per_second
```

### Orchestration Integration

```python
from steer_llm_sdk.orchestration import ReliableOrchestrator

orchestrator = ReliableOrchestrator()
result = await orchestrator.run(request, tool_name="analysis")

# Orchestration metrics include:
# - tool_execution_time_ms
# - retry_count
# - circuit_breaker_state
```

## Configuration

### Basic Configuration

```python
config = MetricsConfig(
    enabled=True,
    batch_size=100,
    request_sampling_rate=1.0,  # Sample 100% of requests
    error_sampling_rate=1.0,    # Sample 100% of errors
    batch_timeout_ms=5000
)
```

### Sampling

```python
# Sample 10% of successful requests, all errors
config = MetricsConfig(
    enabled=True,
    request_sampling_rate=0.1,
    error_sampling_rate=1.0
)
```

### Multiple Sinks

```python
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink, OTelMetricsSink

client = SteerLLMClient(
    metrics_sinks=[
        InMemoryMetricsSink(),  # For debugging
        OTelMetricsSink()       # For production monitoring
    ]
)
```

## Metrics Reference

### Request Metrics
- `duration_ms` - Total request duration
- `time_to_first_token_ms` - Latency to first response
- `prompt_tokens` - Input tokens
- `completion_tokens` - Output tokens
- `cached_tokens` - Cached prompt tokens
- `cost_usd` - Estimated cost

### Streaming Metrics
- `chunks_received` - Number of chunks
- `chunks_per_second` - Throughput
- `throughput_chars_per_second` - Character throughput
- `stream_duration_ms` - Total streaming time

### Reliability Metrics
- `retry_count` - Number of retry attempts
- `circuit_breaker_trips` - Circuit breaker openings
- `fallback_count` - Fallback activations
- `error_category` - Error classification

## Best Practices

1. Enable metrics in production for observability
2. Use sampling for high-traffic applications
3. Implement custom sinks for your monitoring stack
4. Track both successful and failed requests
5. Monitor retry rates and circuit breaker states
6. Set appropriate retention periods for in-memory sinks
7. Use batch processing for performance
