# Phase 5: Reliability Layer - Implementation Plan

## Overview
Phase 5 focuses on hardening the reliability layer to ensure robust error handling, intelligent retry mechanisms, and resilient streaming connections across all providers.

## Current State Analysis

### What Already Exists
1. **Error Infrastructure**
   - `ProviderError` class with retryable flags and retry-after support
   - `ErrorMapper` utility for consistent error mapping across providers
   - All providers use ErrorMapper to convert native errors
   - Error categorization (authentication, rate_limit, server_error, etc.)

2. **Retry Components**
   - `RetryManager` class with exponential backoff
   - `RetryConfig` dataclass for configuration
   - Provider-aware retry decisions based on error type
   - Respect for Retry-After headers

3. **Basic Error Types**
   - AgentError (base)
   - ProviderError, SchemaError, ToolError
   - TimeoutError, BudgetExceededError

### Identified Gaps

1. **Error Type Verification**
   - No comprehensive audit of all possible provider errors
   - Missing error type mappings for edge cases
   - No validation that all errors are properly categorized
   - Insufficient test coverage for error scenarios

2. **Retry Integration**
   - RetryManager exists but not integrated into router/client
   - No retry logic for streaming connections
   - Missing initial connection retry for streams
   - No circuit breaker pattern for repeated failures

3. **Streaming Reliability**
   - No automatic reconnection for interrupted streams
   - Missing backpressure handling
   - No partial response recovery
   - Limited timeout configuration

4. **Observability**
   - No retry metrics or monitoring
   - Missing error rate tracking
   - No alerting on reliability issues
   - Limited debugging information

## Implementation Plan

### Day 1-2: Error Type Audit & Enhancement

#### 1.1 Provider Error Audit
- **OpenAI**: Document all error types from SDK
  - RateLimitError, AuthenticationError, APIError
  - BadRequestError, InternalServerError, APIConnectionError
  - Map each to appropriate ProviderError attributes
  
- **Anthropic**: Document all error types
  - RateLimitError, AuthenticationError, BadRequestError
  - InternalServerError, APIError, APIConnectionError
  - Create comprehensive mapping

- **xAI**: Document all error types
  - Similar to OpenAI but verify specifics
  - Handle any unique error cases

#### 1.2 Enhanced Error Mapping
```python
# steer_llm_sdk/providers/errors.py enhancements
# Building on existing ErrorMapper class
class ErrorClassifier:
    """Enhanced error classification with detailed mappings.
    
    Extends the existing ErrorMapper in steer_llm_sdk/providers/errors.py
    to provide more comprehensive error categorization.
    """
    
    ERROR_MAPPINGS = {
        'openai': {
            'RateLimitError': {'category': 'rate_limit', 'retryable': True},
            'AuthenticationError': {'category': 'auth', 'retryable': False},
            'BadRequestError': {'category': 'validation', 'retryable': False},
            'InternalServerError': {'category': 'server', 'retryable': True},
            'APIConnectionError': {'category': 'network', 'retryable': True},
            'Timeout': {'category': 'timeout', 'retryable': True},
        },
        # Similar for anthropic, xai
    }
```

#### 1.3 Error Testing Suite
- Create `tests/reliability/test_error_mapping.py`
- Test all known error types for each provider
- Verify retryable classification
- Test retry-after extraction

### Day 3-4: Enhanced Retry Manager Integration

**Note**: The existing `RetryManager` in `steer_llm_sdk/reliability/retry.py` provides basic retry functionality. Phase 5 will introduce `EnhancedRetryManager` that wraps and extends the existing implementation with additional features like circuit breakers, streaming retry support, and comprehensive error classification.

#### 2.1 Router Integration
```python
# core/routing/router.py
class LLMRouter:
    def __init__(self):
        # Note: EnhancedRetryManager will supersede the existing RetryManager
        # in reliability/retry.py, wrapping and extending its functionality
        self.retry_manager = EnhancedRetryManager()
        self.default_retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=0.5,
            backoff_factor=2.0,
            max_delay=30.0
        )
```

#### 2.2 Streaming Retry Logic
```python
# reliability/streaming_retry.py
class StreamingRetryManager:
    """Handles retry logic specific to streaming connections."""
    
    async def connect_with_retry(self, connect_func, config):
        """Retry initial streaming connection."""
        
    async def resume_stream(self, stream_state, provider):
        """Resume interrupted stream from last position."""
```

#### 2.3 Circuit Breaker
```python
# reliability/circuit_breaker.py
class CircuitBreaker:
    """Prevent cascading failures with circuit breaker pattern."""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
```

### Day 5: Streaming Reliability

#### 3.1 Connection Resilience
- Implement automatic reconnection for streams
- Add connection health checks
- Handle partial response recovery
- Implement backpressure handling

#### 3.2 Timeout Configuration
```python
# models/streaming.py additions
@dataclass
class StreamingOptions:
    # Existing fields...
    
    # Reliability options
    connection_timeout: float = 30.0
    read_timeout: float = 300.0
    retry_on_connection_error: bool = True
    max_reconnect_attempts: int = 3
    partial_response_recovery: bool = True
```

#### 3.3 Stream State Management
```python
# streaming/state.py
class StreamState:
    """Tracks streaming state for recovery."""
    
    def __init__(self):
        self.chunks_received = []
        self.last_chunk_index = 0
        self.start_time = None
        self.provider_state = {}
```

### Day 6: Testing & Monitoring

#### 4.1 Failure Injection Testing
```python
# tests/reliability/test_failure_injection.py
class FailureInjector:
    """Inject various failure scenarios for testing."""
    
    async def inject_network_error(self, after_chunks=5):
        """Simulate network disconnection."""
    
    async def inject_rate_limit(self, retry_after=60):
        """Simulate rate limit with retry-after."""
    
    async def inject_timeout(self, after_seconds=30):
        """Simulate request timeout."""
```

#### 4.2 Retry Metrics
```python
# observability/reliability_metrics.py
class ReliabilityMetrics:
    """Track reliability metrics for monitoring."""
    
    def record_retry(self, provider, error_type, attempt):
        """Record retry attempt."""
    
    def record_circuit_breaker_state(self, provider, state):
        """Track circuit breaker state changes."""
    
    def get_error_rate(self, provider, window_minutes=5):
        """Calculate error rate over time window."""
```

#### 4.3 Integration Tests
- Test retry behavior for each provider
- Test streaming reconnection
- Test circuit breaker activation
- Test partial response recovery

### Day 7: Documentation & Polish

#### 5.1 Reliability Guide
- Document error types and retry behavior
- Provide configuration examples
- Include troubleshooting guide
- Add monitoring setup instructions

#### 5.2 Migration Guide
- Update existing code to use retry manager
- Configuration migration for timeouts
- Testing recommendations

## File Structure

```
steer_llm_sdk/
├── reliability/
│   ├── __init__.py
│   ├── errors.py           # Enhanced with ErrorClassifier
│   ├── retry.py            # Existing RetryManager (to be wrapped by EnhancedRetryManager)
│   ├── enhanced_retry.py   # NEW: EnhancedRetryManager extending existing functionality
│   ├── streaming_retry.py  # NEW: Streaming-specific retry
│   ├── circuit_breaker.py  # NEW: Circuit breaker pattern
│   └── state.py            # NEW: Stream state management
├── providers/
│   └── errors.py           # Enhanced ErrorMapper with ErrorClassifier extensions
└── tests/
    └── reliability/        # NEW: Comprehensive reliability tests
        ├── test_error_mapping.py
        ├── test_retry_manager.py
        ├── test_streaming_retry.py
        ├── test_circuit_breaker.py
        └── test_failure_injection.py
```

## Success Criteria

1. **Error Coverage**
   - ✅ All known provider errors mapped
   - ✅ 100% test coverage for error scenarios
   - ✅ Accurate retryable classification

2. **Retry Effectiveness**
   - ✅ Automatic retry for transient failures
   - ✅ Respect for rate limits and backoff
   - ✅ No retry storms or cascading failures

3. **Streaming Reliability**
   - ✅ 99.9% stream completion rate
   - ✅ Automatic recovery from interruptions
   - ✅ No data loss on reconnection

4. **Performance Impact**
   - ✅ < 5ms overhead for retry logic
   - ✅ No memory leaks in state management
   - ✅ Efficient circuit breaker checks

## Risk Mitigation

1. **Provider API Changes**
   - Monitor provider SDK updates
   - Maintain error mapping tests
   - Version pin dependencies

2. **Retry Storms**
   - Implement circuit breaker
   - Add jitter to retry delays
   - Monitor retry rates

3. **State Management Complexity**
   - Keep state minimal
   - Add comprehensive logging
   - Implement state cleanup

## Dependencies

- Phase 3 completion (Provider adapters) ✅
- Error mapping infrastructure ✅
- Streaming infrastructure (Phase 4) ✅

## Next Steps

After Phase 5:
- Phase 6: Metrics & Documentation
- Integration with observability layer
- Production monitoring setup