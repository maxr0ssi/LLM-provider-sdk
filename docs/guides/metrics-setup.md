# Metrics Setup Guide

This guide walks you through setting up metrics collection in your Steer LLM SDK application.

## Quick Start

### 1. Basic Setup

```python
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.observability import MetricsConfig
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink

# Create client with metrics enabled
client = SteerLLMClient(
    metrics_config=MetricsConfig(enabled=True),
    metrics_sinks=[InMemoryMetricsSink()]
)

# Use normally - metrics are collected automatically
response = await client.generate("Hello!", model="gpt-4")
```

### 2. Accessing Metrics

```python
# Get the sink
sink = client.metrics_collector.sinks[0]

# Query recent metrics
metrics = await sink.get_metrics(limit=10)
for metric in metrics:
    print(f"{metric.model}: {metric.latency_ms}ms, {metric.total_tokens} tokens")

# Get summary statistics
summary = await sink.get_summary(window_seconds=300)  # Last 5 minutes
print(f"Average latency: {summary.avg_latency_ms}ms")
print(f"Total requests: {summary.count}")
print(f"Error rate: {summary.error_rate:.2%}")
```

## Production Setup

### 1. OpenTelemetry Integration

```python
from steer_llm_sdk.observability.sinks import OTelMetricsSink

# Configure OTLP exporter (via environment variables)
# export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
# export OTEL_SERVICE_NAME=my-llm-service

# Create OTLP sink
otlp_sink = OTelMetricsSink(
    service_name="my-llm-service",
    namespace="production"
)

client = SteerLLMClient(
    metrics_config=MetricsConfig(enabled=True),
    metrics_sinks=[otlp_sink]
)
```

### 2. Prometheus Setup

First, configure OpenTelemetry to export to Prometheus:

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    metrics:
      receivers: [otlp]
      exporters: [prometheus]
```

Then configure Prometheus to scrape the collector:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['localhost:8889']
```

### 3. Grafana Dashboard

Example queries for Grafana:

```promql
# Request rate by model
rate(llm_requests_total[5m])

# Average latency by provider
histogram_quantile(0.5, 
  sum(rate(llm_request_duration_bucket[5m])) by (provider, le)
)

# Token usage rate
rate(llm_tokens_total[5m])

# Error rate
rate(llm_errors_total[5m]) / rate(llm_requests_total[5m])

# Circuit breaker status
llm_circuit_breaker_open
```

## Advanced Configuration

### 1. Selective Metrics

```python
config = MetricsConfig(
    enabled=True,
    
    # Enable/disable specific metrics
    enable_streaming_metrics=True,
    enable_reliability_metrics=True,
    enable_cost_tracking=True,
    
    # Sampling rates (0.0 to 1.0)
    request_sampling_rate=1.0,      # 100% of requests
    streaming_sampling_rate=0.5,    # 50% of streaming
    error_sampling_rate=1.0         # 100% of errors
)
```

### 2. Custom Filters

```python
from steer_llm_sdk.observability import MetricsFilter

class ProductionOnlyFilter(MetricsFilter):
    """Only collect metrics in production."""
    
    def should_collect(self, metric):
        return os.getenv("ENVIRONMENT") == "production"

class HighValueRequestFilter(MetricsFilter):
    """Only track expensive requests."""
    
    def should_collect(self, metric):
        # Track if > 1000 tokens or errors
        return (
            metric.total_tokens > 1000 or 
            metric.error_class is not None
        )

config = MetricsConfig(
    enabled=True,
    filters=[
        ProductionOnlyFilter(),
        HighValueRequestFilter()
    ]
)
```

### 3. Batching for Performance

```python
config = MetricsConfig(
    enabled=True,
    batch_size=100,              # Batch up to 100 metrics
    batch_timeout_seconds=1.0    # Flush every second
)

# For high-volume applications
config = MetricsConfig(
    enabled=True,
    batch_size=500,
    batch_timeout_seconds=5.0,
    request_sampling_rate=0.1    # Sample 10% of requests
)
```

## Multiple Sinks

```python
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink, OTelMetricsSink

# Use multiple sinks for different purposes
client = SteerLLMClient(
    metrics_config=MetricsConfig(enabled=True),
    metrics_sinks=[
        # Production monitoring
        OTelMetricsSink(namespace="prod"),
        
        # Debugging
        InMemoryMetricsSink(max_size=1000),
        
        # Custom sink for data warehouse
        CustomDataWarehouseSink()
    ]
)
```

## Environment-Based Configuration

```python
import os

def create_metrics_config():
    """Create metrics config from environment."""
    return MetricsConfig(
        enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
        batch_size=int(os.getenv("METRICS_BATCH_SIZE", "100")),
        batch_timeout_seconds=float(os.getenv("METRICS_BATCH_TIMEOUT", "1.0")),
        
        # Feature flags
        enable_streaming_metrics=os.getenv("ENABLE_STREAMING_METRICS", "true").lower() == "true",
        enable_reliability_metrics=os.getenv("ENABLE_RELIABILITY_METRICS", "true").lower() == "true",
        enable_cost_tracking=os.getenv("ENABLE_COST_TRACKING", "false").lower() == "true",
        
        # Sampling
        request_sampling_rate=float(os.getenv("REQUEST_SAMPLING_RATE", "1.0")),
        streaming_sampling_rate=float(os.getenv("STREAMING_SAMPLING_RATE", "1.0")),
        error_sampling_rate=float(os.getenv("ERROR_SAMPLING_RATE", "1.0"))
    )

def create_metrics_sinks():
    """Create sinks based on environment."""
    sinks = []
    
    # OTLP sink for production
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        sinks.append(OTelMetricsSink(
            service_name=os.getenv("SERVICE_NAME", "llm-service"),
            namespace=os.getenv("METRICS_NAMESPACE", "default")
        ))
    
    # In-memory for local development
    if os.getenv("ENVIRONMENT") == "development":
        sinks.append(InMemoryMetricsSink())
    
    return sinks

# Create client
client = SteerLLMClient(
    metrics_config=create_metrics_config(),
    metrics_sinks=create_metrics_sinks()
)
```

## FastAPI Integration

```python
from fastapi import FastAPI
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink

app = FastAPI()

# Global metrics sink for debugging
debug_sink = InMemoryMetricsSink()

# Initialize client
client = SteerLLMClient(
    metrics_config=MetricsConfig(enabled=True),
    metrics_sinks=[debug_sink]
)

@app.get("/metrics/summary")
async def metrics_summary(window_seconds: int = 300):
    """Get metrics summary for debugging."""
    summary = await debug_sink.get_summary(window_seconds)
    return {
        "requests": summary.count,
        "avg_latency_ms": summary.avg_latency_ms,
        "p95_latency_ms": summary.p95_latency_ms,
        "error_rate": summary.error_rate,
        "total_tokens": summary.total_tokens,
        "providers": summary.providers,
        "models": summary.models
    }

@app.get("/metrics/recent")
async def recent_metrics(limit: int = 100):
    """Get recent metrics."""
    metrics = await debug_sink.get_metrics(limit=limit)
    return [
        {
            "timestamp": getattr(m, 'timestamp', None),
            "model": m.model,
            "latency_ms": m.latency_ms,
            "tokens": m.input_tokens + m.output_tokens,
            "error": m.error_class
        }
        for m in metrics
    ]

@app.delete("/metrics")
async def clear_metrics():
    """Clear debug metrics."""
    await debug_sink.clear()
    return {"status": "cleared"}

@app.on_event("shutdown")
async def shutdown():
    """Ensure metrics are flushed on shutdown."""
    await client.metrics_collector.flush()
```

## Custom Sink Implementation

```python
from steer_llm_sdk.observability.sinks import MetricsSink
from steer_llm_sdk.observability.metrics import AgentMetrics
import httpx

class HTTPMetricsSink(MetricsSink):
    """Send metrics to HTTP endpoint."""
    
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key
        self.client = httpx.AsyncClient()
        self.buffer = []
        
    async def record(self, metrics: AgentMetrics) -> None:
        """Buffer metrics for batch sending."""
        self.buffer.append({
            "timestamp": time.time(),
            "model": metrics.model,
            "provider": self._extract_provider(metrics.model),
            "latency_ms": metrics.latency_ms,
            "tokens": {
                "input": metrics.input_tokens,
                "output": metrics.output_tokens,
                "cached": metrics.cached_tokens
            },
            "error": metrics.error_class,
            "request_id": metrics.request_id
        })
        
        # Send when buffer is full
        if len(self.buffer) >= 100:
            await self.flush()
    
    async def flush(self) -> None:
        """Send buffered metrics."""
        if not self.buffer:
            return
            
        try:
            await self.client.post(
                self.endpoint,
                json={"metrics": self.buffer},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            self.buffer.clear()
        except Exception as e:
            logger.error(f"Failed to send metrics: {e}")
    
    def _extract_provider(self, model: str) -> str:
        """Extract provider from model name."""
        if model.startswith("gpt"):
            return "openai"
        elif model.startswith("claude"):
            return "anthropic"
        elif model.startswith("grok"):
            return "xai"
        return "unknown"

# Use custom sink
client = SteerLLMClient(
    metrics_sinks=[
        HTTPMetricsSink(
            endpoint="https://metrics.example.com/v1/ingest",
            api_key=os.getenv("METRICS_API_KEY")
        )
    ]
)
```

## Testing with Metrics

```python
import pytest
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink

@pytest.fixture
def client_with_metrics():
    """Client with in-memory metrics for testing."""
    sink = InMemoryMetricsSink()
    client = SteerLLMClient(
        metrics_config=MetricsConfig(enabled=True),
        metrics_sinks=[sink]
    )
    return client, sink

@pytest.mark.asyncio
async def test_request_metrics(client_with_metrics):
    client, sink = client_with_metrics
    
    # Make request
    response = await client.generate("test", model="gpt-4")
    
    # Verify metrics
    metrics = await sink.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].model == "gpt-4"
    assert metrics[0].latency_ms > 0
    
@pytest.mark.asyncio
async def test_error_tracking(client_with_metrics):
    client, sink = client_with_metrics
    
    # Force an error
    with pytest.raises(Exception):
        await client.generate("test", model="invalid-model")
    
    # Check error was recorded
    metrics = await sink.get_metrics()
    assert metrics[0].error_class is not None
```

## Debugging Tips

### 1. Enable Debug Logging

```python
import logging

# Enable debug logs for metrics
logging.getLogger("steer_llm_sdk.observability").setLevel(logging.DEBUG)
```

### 2. Check Metrics Flow

```python
# Verify metrics are being collected
print(f"Collector enabled: {client.metrics_collector.config.enabled}")
print(f"Number of sinks: {len(client.metrics_collector.sinks)}")

# Force flush to see pending metrics
await client.metrics_collector.flush()
```

### 3. Monitor Memory Usage

```python
# For in-memory sink
sink = client.metrics_collector.sinks[0]
if isinstance(sink, InMemoryMetricsSink):
    stats = sink.get_stats()
    print(f"Stored metrics: {stats['stored_metrics']}")
    print(f"Memory usage: ~{stats['stored_metrics'] * 200} bytes")  # Rough estimate
```