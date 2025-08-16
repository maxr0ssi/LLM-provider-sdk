# Reliability Configuration

This guide covers configuration options for reliability features including retry policies, circuit breakers, and error handling.

## Retry Configuration

### Basic Retry Settings

```python
from steer_llm_sdk.reliability import RetryPolicy

# Default retry policy
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
# Retry configuration
export MAX_RETRY_ATTEMPTS=3
export RETRY_INITIAL_DELAY=0.5
export RETRY_BACKOFF_FACTOR=2.0
export RETRY_MAX_DELAY=30.0
export RESPECT_RETRY_AFTER=true
```

### Custom Retry Policies

```python
from steer_llm_sdk.reliability import EnhancedRetryManager, RetryPolicy
from steer_llm_sdk.reliability.error_classifier import ErrorCategory

# Create custom retry policies per error type
retry_manager = EnhancedRetryManager(
    default_policy=RetryPolicy(max_attempts=3),
    category_policies={
        ErrorCategory.RATE_LIMIT: RetryPolicy(
            max_attempts=5,
            initial_delay=1.0,
            backoff_factor=2.0,
            max_delay=60.0,
            respect_retry_after=True
        ),
        ErrorCategory.TIMEOUT: RetryPolicy(
            max_attempts=2,
            initial_delay=0.1,
            backoff_factor=1.5,
            max_delay=5.0
        ),
        ErrorCategory.SERVER_ERROR: RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            backoff_factor=2.0,
            max_delay=30.0
        )
    }
)
```

### Streaming Retry Configuration

```python
from steer_llm_sdk.reliability import StreamingRetryConfig

streaming_config = StreamingRetryConfig(
    max_connection_attempts=3,
    connection_timeout=5.0,
    read_timeout=30.0,
    retry_on_timeout=True,
    preserve_partial_response=True
)

# Environment variables
export STREAMING_CONNECTION_ATTEMPTS=3
export STREAMING_CONNECTION_TIMEOUT=5.0
export STREAMING_READ_TIMEOUT=30.0
export STREAMING_PRESERVE_PARTIAL=true
```

## Circuit Breaker Configuration

### Basic Circuit Breaker

```python
from steer_llm_sdk.reliability import CircuitBreakerConfig

# Per-provider circuit breaker
breaker_config = CircuitBreakerConfig(
    failure_threshold=5,      # Failures before opening
    timeout=60.0,            # Seconds in open state
    half_open_requests=3,    # Test requests in half-open
    window_size=60.0         # Rolling window for failures
)
```

### Environment Variables

```bash
# Circuit breaker settings
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
export CIRCUIT_BREAKER_TIMEOUT=60
export CIRCUIT_BREAKER_HALF_OPEN_REQUESTS=3
export CIRCUIT_BREAKER_WINDOW_SIZE=60
```

### Provider-Specific Circuit Breakers

```python
from steer_llm_sdk.reliability import CircuitBreakerManager

# Configure different thresholds per provider
breaker_manager = CircuitBreakerManager()

# OpenAI - more tolerant
breaker_manager.create_breaker(
    "openai",
    CircuitBreakerConfig(
        failure_threshold=10,
        timeout=30.0,
        half_open_requests=5
    )
)

# Anthropic - standard
breaker_manager.create_breaker(
    "anthropic",
    CircuitBreakerConfig(
        failure_threshold=5,
        timeout=60.0,
        half_open_requests=3
    )
)

# xAI - more strict
breaker_manager.create_breaker(
    "xai",
    CircuitBreakerConfig(
        failure_threshold=3,
        timeout=120.0,
        half_open_requests=1
    )
)
```

## Error Classification

### Error Categories

```python
from steer_llm_sdk.reliability import ErrorClassifier

# Default error classification patterns
ERROR_PATTERNS = {
    "rate_limit": [
        "rate limit", "too many requests", "quota exceeded",
        "throttled", "retry later", "request limit"
    ],
    "authentication": [
        "unauthorized", "invalid api key", "authentication failed",
        "forbidden", "invalid credentials"
    ],
    "timeout": [
        "timeout", "timed out", "deadline exceeded",
        "connection timeout", "read timeout"
    ],
    "server_error": [
        "internal server error", "503", "502", "500",
        "service unavailable", "gateway timeout"
    ]
}
```

### Custom Error Classification

```python
from steer_llm_sdk.reliability import ErrorClassifier

class CustomErrorClassifier(ErrorClassifier):
    """Extended error classifier with custom patterns."""
    
    def __init__(self):
        super().__init__()
        
        # Add custom patterns
        self.patterns["billing"] = [
            "payment required", "billing", "subscription",
            "insufficient credits", "payment failed"
        ]
        
        self.patterns["content_policy"] = [
            "content policy", "safety", "violation",
            "inappropriate", "blocked content"
        ]
    
    def is_retryable(self, error) -> bool:
        """Custom retry logic."""
        category = self.classify(error)
        
        # Don't retry billing or content policy errors
        if category in ["billing", "content_policy"]:
            return False
            
        # Use default logic for others
        return super().is_retryable(error)
```

## Reliability Policies

### Global Configuration

```python
from steer_llm_sdk.core.routing import LLMRouter
from steer_llm_sdk.reliability import ReliabilityConfig

# Create router with custom reliability config
reliability_config = ReliabilityConfig(
    enable_retry=True,
    enable_circuit_breaker=True,
    enable_fallback=True,
    fallback_models={
        "gpt-4": ["gpt-3.5-turbo"],
        "claude-3-opus": ["claude-3-sonnet"],
        "grok-1": ["gpt-4"]
    }
)

router = LLMRouter(reliability_config=reliability_config)
```

### Per-Request Configuration

```python
# Override reliability settings per request
response = await client.generate(
    messages="Important request",
    model="gpt-4",
    retry_config={
        "max_attempts": 5,
        "initial_delay": 1.0
    },
    circuit_breaker_enabled=False  # Disable for this request
)
```

## Monitoring Reliability

### Metrics Collection

```python
# Automatic reliability metrics
from steer_llm_sdk.observability import MetricsConfig

metrics_config = MetricsConfig(
    enable_reliability_metrics=True
)

# Metrics collected:
# - retry_attempts
# - retry_successes
# - circuit_breaker_trips
# - fallback_uses
# - error_categories
```

### Reliability Dashboard

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/reliability/status")
async def reliability_status():
    """Get current reliability status."""
    return {
        "circuit_breakers": {
            "openai": router.circuit_manager.get_state("openai"),
            "anthropic": router.circuit_manager.get_state("anthropic"),
            "xai": router.circuit_manager.get_state("xai")
        },
        "retry_stats": router.retry_manager.get_metrics(),
        "error_distribution": router.get_error_distribution()
    }

@app.post("/reliability/circuit-breaker/{provider}/reset")
async def reset_circuit_breaker(provider: str):
    """Manually reset a circuit breaker."""
    router.circuit_manager.reset(provider)
    return {"status": "reset", "provider": provider}
```

## Advanced Configurations

### Adaptive Retry

```python
class AdaptiveRetryPolicy(RetryPolicy):
    """Retry policy that adapts based on success rate."""
    
    def __init__(self):
        super().__init__()
        self.success_rate = 1.0
        self.attempt_history = deque(maxlen=100)
    
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Adapt retry decision based on history."""
        # Track attempt
        self.attempt_history.append({
            "attempt": attempt,
            "error": type(error).__name__,
            "timestamp": time.time()
        })
        
        # Calculate recent success rate
        recent = list(self.attempt_history)[-20:]
        if recent:
            failures = sum(1 for a in recent if a["attempt"] > 1)
            self.success_rate = 1 - (failures / len(recent))
        
        # More aggressive retry if success rate is high
        if self.success_rate > 0.8:
            return attempt < self.max_attempts + 2
        elif self.success_rate < 0.5:
            return attempt < max(2, self.max_attempts - 1)
        else:
            return attempt < self.max_attempts
```

### Health-Based Circuit Breaking

```python
class HealthAwareCircuitBreaker(CircuitBreaker):
    """Circuit breaker that considers provider health."""
    
    async def should_allow_request(self) -> bool:
        """Check both circuit state and provider health."""
        # Check circuit state
        if not await super().should_allow_request():
            return False
        
        # Check provider health endpoint
        health = await self.check_provider_health()
        if health["status"] == "degraded":
            # More conservative in degraded state
            self.config.failure_threshold = 3
        elif health["status"] == "healthy":
            # Normal thresholds
            self.config.failure_threshold = 5
            
        return health["status"] != "down"
    
    async def check_provider_health(self) -> dict:
        """Check provider health endpoint."""
        # Implementation depends on provider
        return {"status": "healthy"}
```

## Best Practices

1. **Start with defaults** - The default configuration works well for most cases
2. **Monitor metrics** - Track retry rates and circuit breaker trips
3. **Tune gradually** - Adjust thresholds based on observed patterns
4. **Provider-specific** - Different providers need different settings
5. **Error classification** - Properly classify errors for appropriate handling
6. **Respect rate limits** - Always honor retry-after headers
7. **Circuit breaker recovery** - Allow sufficient time for recovery
8. **Partial responses** - Preserve partial streaming responses when possible
9. **Fallback strategies** - Have backup models for critical requests
10. **Alert on patterns** - Set up alerts for unusual error patterns

## Troubleshooting

### High Retry Rate

```python
# Check retry metrics
metrics = router.retry_manager.get_metrics()
print(f"Retry rate: {metrics.retry_rate:.2%}")
print(f"Most common errors: {metrics.top_errors}")

# Adjust if needed
if metrics.retry_rate > 0.2:  # >20% retry rate
    # Investigate root cause
    # Consider adjusting thresholds or fixing upstream issues
    pass
```

### Circuit Breaker Stuck Open

```python
# Check circuit breaker state
state = router.circuit_manager.get_detailed_state("openai")
print(f"State: {state['state']}")
print(f"Failures: {state['failure_count']}")
print(f"Last failure: {state['last_failure_time']}")

# Manual intervention if needed
if state['state'] == 'OPEN' and time.time() - state['last_failure_time'] > 300:
    # Been open for >5 minutes, try reset
    router.circuit_manager.reset("openai")
```