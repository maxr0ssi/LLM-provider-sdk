# Creating Custom Metrics Sinks

This guide shows how to create custom metrics sinks for the Steer LLM SDK to integrate with your monitoring infrastructure.

## Sink Protocol

All metrics sinks must implement the `MetricsSink` protocol:

```python
from typing import Protocol
from steer_llm_sdk.observability.metrics import AgentMetrics

class MetricsSink(Protocol):
    """Protocol for metrics sink implementations."""
    
    async def record(self, metrics: AgentMetrics) -> None:
        """Record metrics data."""
        ...
    
    async def flush(self) -> None:
        """Flush any buffered metrics."""
        ...
```

## Example Implementations

### 1. CloudWatch Sink

```python
import boto3
import time
from datetime import datetime
from typing import List, Dict, Any
from steer_llm_sdk.observability.sinks import MetricsSink
from steer_llm_sdk.observability.metrics import AgentMetrics

class CloudWatchMetricsSink(MetricsSink):
    """Send metrics to AWS CloudWatch."""
    
    def __init__(self, namespace: str = "LLM/Metrics", region: str = "us-east-1"):
        self.namespace = namespace
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.buffer: List[Dict[str, Any]] = []
        self.buffer_size = 20  # CloudWatch limit
        
    async def record(self, metrics: AgentMetrics) -> None:
        """Record metric to buffer."""
        # Create CloudWatch metric data
        metric_data = {
            'MetricName': 'RequestLatency',
            'Value': metrics.latency_ms,
            'Unit': 'Milliseconds',
            'Timestamp': datetime.utcnow(),
            'Dimensions': [
                {'Name': 'Model', 'Value': metrics.model},
                {'Name': 'Provider', 'Value': self._extract_provider(metrics.model)},
            ]
        }
        
        if metrics.error_class:
            metric_data['Dimensions'].append({
                'Name': 'ErrorType', 
                'Value': metrics.error_class
            })
        
        self.buffer.append(metric_data)
        
        # Also track token usage
        if metrics.input_tokens + metrics.output_tokens > 0:
            self.buffer.append({
                'MetricName': 'TokenUsage',
                'Value': metrics.input_tokens + metrics.output_tokens,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow(),
                'Dimensions': [
                    {'Name': 'Model', 'Value': metrics.model},
                    {'Name': 'TokenType', 'Value': 'total'},
                ]
            })
        
        # Flush if buffer is full
        if len(self.buffer) >= self.buffer_size:
            await self.flush()
    
    async def flush(self) -> None:
        """Send buffered metrics to CloudWatch."""
        if not self.buffer:
            return
            
        try:
            # CloudWatch put_metric_data is synchronous
            # In production, consider using aioboto3
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=self.buffer[:self.buffer_size]
            )
            # Keep any overflow
            self.buffer = self.buffer[self.buffer_size:]
        except Exception as e:
            print(f"Failed to send metrics to CloudWatch: {e}")
    
    def _extract_provider(self, model: str) -> str:
        """Extract provider from model name."""
        if model.startswith("gpt"):
            return "openai"
        elif model.startswith("claude"):
            return "anthropic"
        elif model.startswith("grok"):
            return "xai"
        return "unknown"
```

### 2. Datadog Sink

```python
import httpx
import json
from typing import List, Dict, Any
from steer_llm_sdk.observability.sinks import MetricsSink
from steer_llm_sdk.observability.metrics import AgentMetrics

class DatadogMetricsSink(MetricsSink):
    """Send metrics to Datadog."""
    
    def __init__(self, api_key: str, site: str = "datadoghq.com"):
        self.api_key = api_key
        self.api_url = f"https://api.{site}/api/v2/series"
        self.client = httpx.AsyncClient()
        self.buffer: List[Dict[str, Any]] = []
        
    async def record(self, metrics: AgentMetrics) -> None:
        """Convert and buffer metrics for Datadog."""
        timestamp = int(time.time())
        
        # Base tags
        tags = [
            f"model:{metrics.model}",
            f"provider:{self._extract_provider(metrics.model)}",
        ]
        
        if metrics.error_class:
            tags.append(f"error:{metrics.error_class}")
            tags.append("status:error")
        else:
            tags.append("status:success")
        
        # Latency metric
        self.buffer.append({
            "metric": "llm.request.latency",
            "type": 3,  # Gauge
            "points": [{
                "timestamp": timestamp,
                "value": metrics.latency_ms
            }],
            "tags": tags
        })
        
        # Token metrics
        if metrics.input_tokens > 0:
            self.buffer.append({
                "metric": "llm.tokens.input",
                "type": 0,  # Count
                "points": [{
                    "timestamp": timestamp,
                    "value": metrics.input_tokens
                }],
                "tags": tags
            })
        
        if metrics.output_tokens > 0:
            self.buffer.append({
                "metric": "llm.tokens.output",
                "type": 0,  # Count
                "points": [{
                    "timestamp": timestamp,
                    "value": metrics.output_tokens
                }],
                "tags": tags
            })
        
        # Retry metric
        if metrics.retries > 0:
            self.buffer.append({
                "metric": "llm.retries",
                "type": 0,  # Count
                "points": [{
                    "timestamp": timestamp,
                    "value": metrics.retries
                }],
                "tags": tags
            })
        
        # Flush if buffer is large
        if len(self.buffer) >= 100:
            await self.flush()
    
    async def flush(self) -> None:
        """Send metrics to Datadog."""
        if not self.buffer:
            return
            
        try:
            response = await self.client.post(
                self.api_url,
                headers={
                    "DD-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json={"series": self.buffer}
            )
            response.raise_for_status()
            self.buffer.clear()
        except Exception as e:
            print(f"Failed to send metrics to Datadog: {e}")
    
    def _extract_provider(self, model: str) -> str:
        if model.startswith("gpt"):
            return "openai"
        elif model.startswith("claude"):
            return "anthropic"
        elif model.startswith("grok"):
            return "xai"
        return "unknown"
```

### 3. InfluxDB Sink

```python
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import ASYNCHRONOUS
from steer_llm_sdk.observability.sinks import MetricsSink
from steer_llm_sdk.observability.metrics import AgentMetrics

class InfluxDBMetricsSink(MetricsSink):
    """Send metrics to InfluxDB."""
    
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=ASYNCHRONOUS)
        self.bucket = bucket
        self.org = org
        
    async def record(self, metrics: AgentMetrics) -> None:
        """Write metrics to InfluxDB."""
        # Create point
        point = Point("llm_request") \
            .tag("model", metrics.model) \
            .tag("provider", self._extract_provider(metrics.model)) \
            .field("latency_ms", metrics.latency_ms) \
            .field("prompt_tokens", metrics.input_tokens) \
            .field("completion_tokens", metrics.output_tokens) \
            .field("total_tokens", metrics.input_tokens + metrics.output_tokens)
        
        if metrics.cached_tokens > 0:
            point.field("cached_tokens", metrics.cached_tokens)
        
        if metrics.error_class:
            point.tag("error", metrics.error_class)
            point.tag("status", "error")
        else:
            point.tag("status", "success")
        
        if metrics.retries > 0:
            point.field("retries", metrics.retries)
        
        # Write point
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)
    
    async def flush(self) -> None:
        """Flush is handled by the async write API."""
        # InfluxDB client handles batching internally
        pass
    
    def _extract_provider(self, model: str) -> str:
        if model.startswith("gpt"):
            return "openai"
        elif model.startswith("claude"):
            return "anthropic"
        elif model.startswith("grok"):
            return "xai"
        return "unknown"
    
    def __del__(self):
        """Close client on cleanup."""
        if hasattr(self, 'client'):
            self.client.close()
```

### 4. PostgreSQL Sink

```python
import asyncpg
import json
from datetime import datetime
from steer_llm_sdk.observability.sinks import MetricsSink
from steer_llm_sdk.observability.metrics import AgentMetrics

class PostgreSQLMetricsSink(MetricsSink):
    """Store metrics in PostgreSQL."""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None
        
    async def _ensure_pool(self):
        """Ensure connection pool exists."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(self.connection_string)
            
            # Create table if not exists
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS llm_metrics (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ DEFAULT NOW(),
                        request_id TEXT,
                        model TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        method TEXT,
                        latency_ms INTEGER NOT NULL,
                        prompt_tokens INTEGER DEFAULT 0,
                        completion_tokens INTEGER DEFAULT 0,
                        cached_tokens INTEGER DEFAULT 0,
                        total_cost DECIMAL(10, 6),
                        error_class TEXT,
                        retries INTEGER DEFAULT 0,
                        metadata JSONB
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_timestamp ON llm_metrics(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_model ON llm_metrics(model);
                    CREATE INDEX IF NOT EXISTS idx_provider ON llm_metrics(provider);
                    CREATE INDEX IF NOT EXISTS idx_error ON llm_metrics(error_class);
                ''')
    
    async def record(self, metrics: AgentMetrics) -> None:
        """Insert metrics into PostgreSQL."""
        await self._ensure_pool()
        
        provider = self._extract_provider(metrics.model)
        
        # Calculate estimated cost (simplified)
        cost = self._estimate_cost(
            metrics.model,
            metrics.input_tokens,
            metrics.output_tokens
        )
        
        # Additional metadata
        metadata = {
            "tools_used": metrics.tools_used,
            "trace_id": metrics.trace_id,
        }
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO llm_metrics (
                    request_id, model, provider, latency_ms,
                    prompt_tokens, completion_tokens, cached_tokens,
                    total_cost, error_class, retries, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ''',
                metrics.request_id,
                metrics.model,
                provider,
                metrics.latency_ms,
                metrics.input_tokens,
                metrics.output_tokens,
                metrics.cached_tokens,
                cost,
                metrics.error_class,
                metrics.retries,
                json.dumps(metadata)
            )
    
    async def flush(self) -> None:
        """No buffering, each metric is inserted immediately."""
        pass
    
    def _extract_provider(self, model: str) -> str:
        if model.startswith("gpt"):
            return "openai"
        elif model.startswith("claude"):
            return "anthropic"
        elif model.startswith("grok"):
            return "xai"
        return "unknown"
    
    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on model and tokens."""
        # Simplified pricing (cents per 1K tokens)
        pricing = {
            "gpt-4": {"input": 3.0, "output": 6.0},
            "gpt-3.5-turbo": {"input": 0.05, "output": 0.15},
            "claude-3-opus": {"input": 1.5, "output": 7.5},
            "claude-3-sonnet": {"input": 0.3, "output": 1.5},
        }
        
        # Find matching price
        for model_prefix, prices in pricing.items():
            if model.startswith(model_prefix):
                input_cost = (input_tokens / 1000) * prices["input"] / 100
                output_cost = (output_tokens / 1000) * prices["output"] / 100
                return input_cost + output_cost
        
        return 0.0
    
    async def get_summary_stats(self, hours: int = 24):
        """Query summary statistics."""
        await self._ensure_pool()
        
        async with self.pool.acquire() as conn:
            return await conn.fetchrow('''
                SELECT 
                    COUNT(*) as total_requests,
                    AVG(latency_ms) as avg_latency,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
                    SUM(prompt_tokens + completion_tokens) as total_tokens,
                    SUM(total_cost) as total_cost,
                    COUNT(*) FILTER (WHERE error_class IS NOT NULL) as error_count
                FROM llm_metrics
                WHERE timestamp > NOW() - INTERVAL '%s hours'
            ''', hours)
```

## Best Practices

### 1. Error Handling

Always handle errors gracefully:

```python
class ResilientMetricsSink(MetricsSink):
    async def record(self, metrics: AgentMetrics) -> None:
        try:
            # Your recording logic
            await self._do_record(metrics)
        except Exception as e:
            # Log but don't crash
            logger.error(f"Failed to record metrics: {e}")
    
    async def flush(self) -> None:
        try:
            await self._do_flush()
        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")
```

### 2. Buffering

Implement buffering for efficiency:

```python
class BufferedMetricsSink(MetricsSink):
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.buffer = []
        self.lock = asyncio.Lock()
    
    async def record(self, metrics: AgentMetrics) -> None:
        async with self.lock:
            self.buffer.append(metrics)
            if len(self.buffer) >= self.batch_size:
                await self._flush_buffer()
    
    async def flush(self) -> None:
        async with self.lock:
            await self._flush_buffer()
    
    async def _flush_buffer(self) -> None:
        if not self.buffer:
            return
        
        # Send batch
        await self._send_batch(self.buffer)
        self.buffer.clear()
```

### 3. Async Operations

Use async operations for I/O:

```python
class AsyncMetricsSink(MetricsSink):
    def __init__(self):
        self.session = httpx.AsyncClient()
    
    async def record(self, metrics: AgentMetrics) -> None:
        # Use async HTTP client
        await self.session.post(
            "https://api.example.com/metrics",
            json=self._serialize(metrics)
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.session.aclose()
```

### 4. Resource Cleanup

Properly clean up resources:

```python
class ManagedMetricsSink(MetricsSink):
    async def initialize(self):
        """Initialize resources."""
        self.connection = await create_connection()
    
    async def cleanup(self):
        """Clean up resources."""
        await self.flush()
        if hasattr(self, 'connection'):
            await self.connection.close()
    
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, *args):
        await self.cleanup()
```

## Testing Custom Sinks

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_custom_sink():
    # Create sink with mocked backend
    sink = CustomMetricsSink()
    sink._send_to_backend = AsyncMock()
    
    # Create test metric
    metric = AgentMetrics(
        model="gpt-4",
        latency_ms=150,
        input_tokens=100,
        output_tokens=200
    )
    
    # Record metric
    await sink.record(metric)
    
    # Verify it was sent
    sink._send_to_backend.assert_called_once()
    
    # Test flush
    await sink.flush()

@pytest.mark.asyncio
async def test_sink_error_handling():
    sink = CustomMetricsSink()
    
    # Make backend fail
    sink._send_to_backend = AsyncMock(side_effect=Exception("Network error"))
    
    # Should not raise
    metric = AgentMetrics(model="gpt-4", latency_ms=100)
    await sink.record(metric)  # Should handle error gracefully
```

## Usage Example

```python
from steer_llm_sdk import SteerLLMClient

# Create custom sinks
cloudwatch_sink = CloudWatchMetricsSink(namespace="MyApp/LLM")
datadog_sink = DatadogMetricsSink(api_key=os.getenv("DD_API_KEY"))
postgres_sink = PostgreSQLMetricsSink(
    "postgresql://user:pass@localhost/metrics"
)

# Initialize client with multiple sinks
client = SteerLLMClient(
    metrics_config=MetricsConfig(enabled=True),
    metrics_sinks=[cloudwatch_sink, datadog_sink, postgres_sink]
)

# Use normally - metrics go to all sinks
response = await client.generate("Hello!", model="gpt-4")

# Don't forget to flush on shutdown
await client.metrics_collector.flush()
```