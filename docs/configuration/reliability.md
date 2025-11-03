# Reliability Configuration

Configure retry policies, circuit breakers, and error handling.

## Retry Configuration

### Basic Settings

```python
from steer_llm_sdk.reliability import RetryPolicy

default_policy = RetryPolicy(
    max_attempts=3,
    initial_delay=0.5,  # seconds
    backoff_factor=2.0,
    max_delay=30.0,
    respect_retry_after=True
)
```

### Environment Variables

```bash
export MAX_RETRY_ATTEMPTS=3
export RETRY_INITIAL_DELAY=0.5
export RETRY_BACKOFF_FACTOR=2.0
export RETRY_MAX_DELAY=30.0
export RESPECT_RETRY_AFTER=true
```

### Per-Error Type Policies

```python
from steer_llm_sdk.reliability import AdvancedRetryManager, RetryPolicy
from steer_llm_sdk.reliability.error_classifier import ErrorCategory

retry_manager = AdvancedRetryManager(
    default_policy=RetryPolicy(max_attempts=3),
    category_policies={
        ErrorCategory.RATE_LIMIT: RetryPolicy(
            max_attempts=5,
            initial_delay=1.0,
            respect_retry_after=True
        ),
        ErrorCategory.TIMEOUT: RetryPolicy(
            max_attempts=2,
            initial_delay=0.1,
            max_delay=5.0
        )
    }
)
```

### Streaming Retry

```python
from steer_llm_sdk.reliability import StreamingRetryConfig

streaming_config = StreamingRetryConfig(
    max_connection_attempts=3,
    connection_timeout=5.0,
    read_timeout=30.0,
    retry_on_timeout=True,
    preserve_partial_response=True
)
```

## Circuit Breaker Configuration

### Basic Circuit Breaker

```python
from steer_llm_sdk.reliability import CircuitBreakerConfig

breaker_config = CircuitBreakerConfig(
    failure_threshold=5,      # Failures before opening
    timeout=60.0,            # Seconds in open state
    half_open_requests=3,    # Test requests in half-open
    window_size=60.0         # Rolling window for failures
)
```

### Environment Variables

```bash
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
export CIRCUIT_BREAKER_TIMEOUT=60
export CIRCUIT_BREAKER_HALF_OPEN_REQUESTS=3
export CIRCUIT_BREAKER_WINDOW_SIZE=60
```

### Provider-Specific Breakers

```python
from steer_llm_sdk.reliability import CircuitBreakerManager

breaker_manager = CircuitBreakerManager()

# Configure per provider
breaker_manager.create_breaker("openai", CircuitBreakerConfig(
    failure_threshold=10,
    timeout=30.0
))

breaker_manager.create_breaker("anthropic", CircuitBreakerConfig(
    failure_threshold=5,
    timeout=60.0
))
```

## Error Classification

### Default Patterns

```python
ERROR_PATTERNS = {
    "rate_limit": [
        "rate limit", "too many requests", "quota exceeded",
        "throttled", "retry later"
    ],
    "authentication": [
        "unauthorized", "invalid api key", "authentication failed"
    ],
    "timeout": [
        "timeout", "timed out", "deadline exceeded"
    ],
    "server_error": [
        "internal server error", "503", "502", "500",
        "service unavailable"
    ]
}
```

### Custom Classification

```python
from steer_llm_sdk.reliability import ErrorClassifier

class CustomErrorClassifier(ErrorClassifier):
    def __init__(self):
        super().__init__()
        # Add custom patterns
        self.patterns["billing"] = ["payment required", "insufficient credits"]
        self.patterns["content_policy"] = ["content policy", "violation"]

    def is_retryable(self, error) -> bool:
        category = self.classify(error)
        # Don't retry billing or content policy errors
        if category in ["billing", "content_policy"]:
            return False
        return super().is_retryable(error)
```

## Global Configuration

```python
from steer_llm_sdk.core.routing import LLMRouter
from steer_llm_sdk.reliability import ReliabilityConfig

reliability_config = ReliabilityConfig(
    enable_retry=True,
    enable_circuit_breaker=True,
    enable_fallback=True,
    fallback_models={
        "gpt-4": ["gpt-3.5-turbo"],
        "claude-3-opus": ["claude-3-sonnet"]
    }
)

router = LLMRouter(reliability_config=reliability_config)
```

## Per-Request Override

```python
response = await client.generate(
    messages="Important request",
    model="gpt-4",
    retry_config={
        "max_attempts": 5,
        "initial_delay": 1.0
    },
    circuit_breaker_enabled=False
)
```

## Best Practices

1. Start with defaults - they work well for most cases
2. Monitor retry rates and circuit breaker trips
3. Tune thresholds gradually based on observed patterns
4. Configure different settings per provider
5. Always honor retry-after headers
6. Preserve partial streaming responses when possible
7. Set up alerts for unusual error patterns
