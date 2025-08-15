# Configuration Reference

This directory contains configuration documentation for the Steer LLM SDK.

## Configuration Files

- [Providers Configuration](./providers.md) - Provider-specific settings and API keys
- [Reliability Configuration](./reliability.md) - Retry policies and circuit breaker settings
- [Streaming Configuration](./streaming.md) - Streaming options and performance tuning

## Environment Variables

### Core Settings

```bash
# Provider API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
XAI_API_KEY=xai-...

# SDK Behavior
STEER_SDK_BYPASS_AVAILABILITY_CHECK=false
STEER_STREAMING_STATE_TTL=900  # seconds

# Metrics
METRICS_ENABLED=true
METRICS_BATCH_SIZE=100
REQUEST_SAMPLING_RATE=1.0
```

### Provider Selection

```bash
# Default provider/model
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o-mini

# Provider endpoints (optional)
OPENAI_API_BASE=https://api.openai.com/v1
ANTHROPIC_API_BASE=https://api.anthropic.com
```

### Reliability Settings

```bash
# Retry configuration
MAX_RETRY_ATTEMPTS=3
RETRY_INITIAL_DELAY=0.5
RETRY_BACKOFF_FACTOR=2.0
RETRY_MAX_DELAY=30.0

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60
CIRCUIT_BREAKER_HALF_OPEN_REQUESTS=3
```

## Configuration Objects

### Client Configuration

```python
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.observability import MetricsConfig

client = SteerLLMClient(
    metrics_config=MetricsConfig(
        enabled=True,
        batch_size=100,
        request_sampling_rate=1.0
    )
)
```

### Streaming Configuration

```python
from steer_llm_sdk.models.streaming import StreamingOptions

options = StreamingOptions(
    enable_usage_aggregation=True,
    prefer_tiktoken=True,
    enable_json_stream_handler=True,
    connection_timeout=5.0,
    read_timeout=30.0
)
```

## Configuration Precedence

1. Explicit parameters in code
2. Environment variables
3. Configuration files
4. Default values

## Best Practices

1. **Use environment variables** for sensitive data (API keys)
2. **Version control** configuration files (except secrets)
3. **Document** all custom configuration
4. **Test** configuration changes in staging first
5. **Monitor** the impact of configuration changes