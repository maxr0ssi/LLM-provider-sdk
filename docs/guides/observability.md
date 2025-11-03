# Observability Guide

Configure metrics and monitoring for your LLM application.

## Quick Start

```python
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.observability.sinks import ConsoleSink

# Enable console metrics (development)
client = SteerLLMClient(metrics_sink=ConsoleSink())

response = await client.generate(
    messages="Hello, world!",
    model="gpt-4o-mini"
)

# Metrics printed to console:
# Model: gpt-4o-mini
# Latency: 234ms
# Tokens: 10 input, 5 output
# Cost: $0.000023
```

## Available Metrics

Each request emits a `Metrics` object with:

| Field | Type | Description |
|-------|------|-------------|
| timestamp | float | Request timestamp |
| model | str | Model identifier |
| provider | str | Provider name |
| latency_ms | float | Request duration |
| input_tokens | int | Prompt tokens |
| output_tokens | int | Generated tokens |
| cost_usd | float | Estimated cost |
| success | bool | Request success |
| error_class | str | Error type if failed |
| streaming | bool | Was streaming request |

## Custom Metrics Sink

Implement the `MetricsSink` interface to send metrics to your observability platform:

```python
from steer_llm_sdk.observability.sinks import MetricsSink
from steer_llm_sdk.models.metrics import Metrics

class CustomSink(MetricsSink):
    """Send metrics to your custom backend."""

    def __init__(self, api_endpoint: str, api_key: str):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.session = None

    async def initialize(self) -> None:
        """Set up HTTP client or connections."""
        import httpx
        self.session = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}"}
        )

    async def emit(self, metrics: Metrics) -> None:
        """Send metrics to backend."""
        payload = {
            "timestamp": metrics.timestamp,
            "model": metrics.model,
            "provider": metrics.provider,
            "latency_ms": metrics.latency_ms,
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "cost_usd": metrics.cost_usd,
            "success": metrics.success,
            "error_class": metrics.error_class
        }

        await self.session.post(
            f"{self.api_endpoint}/metrics",
            json=payload
        )

    async def flush(self) -> None:
        """Flush any buffered metrics."""
        pass

    async def close(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.aclose()
```

## Using Custom Sinks

```python
# Create client with custom sink
sink = CustomSink(
    api_endpoint="https://metrics.example.com",
    api_key="your-api-key"
)

client = SteerLLMClient(metrics_sink=sink)

# Metrics are automatically sent to your sink
response = await client.generate(
    messages="Hello, world!",
    model="gpt-4o-mini"
)
```

## Buffered Sink

For high-throughput scenarios, buffer metrics before sending:

```python
class BufferedSink(MetricsSink):
    def __init__(self, backend_url: str, buffer_size: int = 100):
        self.backend_url = backend_url
        self.buffer_size = buffer_size
        self.buffer = []

    async def emit(self, metrics: Metrics) -> None:
        self.buffer.append(metrics)
        if len(self.buffer) >= self.buffer_size:
            await self.flush()

    async def flush(self) -> None:
        if not self.buffer:
            return

        # Send batch to backend
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.backend_url}/batch",
                json=[m.dict() for m in self.buffer]
            )

        self.buffer.clear()
```

## Disabling Metrics

```python
from steer_llm_sdk.observability.sinks import NoOpSink

# Disable metrics collection
client = SteerLLMClient(metrics_sink=NoOpSink())
```

## Streaming Metrics

Streaming requests include additional metrics:

```python
response = await client.stream_with_usage(
    messages="Write a story",
    model="gpt-4o-mini"
)

# Metrics include streaming-specific data
# - Time to first token
# - Chunks per second
# - Total streaming duration
```

## Cost Tracking

The SDK automatically calculates costs based on token usage and model pricing:

```python
response = await client.generate(
    messages="Analyze this text",
    model="gpt-4o-mini"
)

print(f"Cost: ${response.cost_usd:.6f}")
print(f"Input: ${response.cost_breakdown['input_cost']:.6f}")
print(f"Output: ${response.cost_breakdown['output_cost']:.6f}")
```

See [Pricing Guide](../pricing.md) for pricing information.

## Production Best Practices

For production deployments, implement a custom sink that:

1. **Buffers metrics** - Batch sends to reduce overhead
2. **Handles failures gracefully** - Retry failed sends with exponential backoff
3. **Uses async HTTP clients** - Non-blocking network operations
4. **Implements proper error handling** - Don't let metrics collection break your app
5. **Samples high-volume metrics** - Reduce costs for high-traffic applications

## Built-in Sinks

The SDK includes these sinks:
- `ConsoleSink` - Print metrics to stdout (development only)
- `NoOpSink` - Discard metrics (default)

To add more sinks (Prometheus, Datadog, CloudWatch, etc.), implement the `MetricsSink` interface.
