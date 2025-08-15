# Phase 5: Reliability Layer - Technical Design

## Architecture Overview

The reliability layer provides a comprehensive framework for handling errors, retries, and connection resilience across all LLM providers. It integrates seamlessly with the existing streaming infrastructure while adding minimal overhead.

```
┌─────────────────────────────────────────────────────────────┐
│                        Client API                            │
├─────────────────────────────────────────────────────────────┤
│                         Router                               │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Retry Manager  │  │Circuit Breaker│  │ Error Mapper  │  │
│  └─────────────────┘  └──────────────┘  └───────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    Provider Adapters                         │
│  ┌─────────┐     ┌───────────┐     ┌─────────────────┐     │
│  │ OpenAI  │     │ Anthropic │     │      xAI        │     │
│  └─────────┘     └───────────┘     └─────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Enhanced Error Classification

```python
# reliability/errors.py

from enum import Enum
from typing import Dict, Optional, Type, Any
from dataclasses import dataclass

class ErrorCategory(Enum):
    """Standard error categories across all providers."""
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    SERVER_ERROR = "server_error"
    NETWORK = "network"
    TIMEOUT = "timeout"
    CONTENT_FILTER = "content_filter"
    UNKNOWN = "unknown"

@dataclass
class ErrorClassification:
    """Detailed error classification."""
    category: ErrorCategory
    is_retryable: bool
    suggested_delay: Optional[float] = None
    user_message: Optional[str] = None
    
class ErrorClassifier:
    """Enhanced error classification system."""
    
    # Comprehensive error mappings
    ERROR_PATTERNS = {
        # OpenAI patterns
        'rate_limit_exceeded': ErrorCategory.RATE_LIMIT,
        'insufficient_quota': ErrorCategory.RATE_LIMIT,
        'invalid_api_key': ErrorCategory.AUTHENTICATION,
        'model_not_found': ErrorCategory.VALIDATION,
        'context_length_exceeded': ErrorCategory.VALIDATION,
        'content_filter': ErrorCategory.CONTENT_FILTER,
        'server_error': ErrorCategory.SERVER_ERROR,
        'engine_overloaded': ErrorCategory.SERVER_ERROR,
        
        # Network patterns
        'connection_error': ErrorCategory.NETWORK,
        'timeout': ErrorCategory.TIMEOUT,
        'dns_resolution': ErrorCategory.NETWORK,
    }
    
    @classmethod
    def classify_error(cls, error: Exception, provider: str) -> ErrorClassification:
        """Classify an error with detailed metadata."""
        # Provider-specific classification
        if provider == "openai":
            return cls._classify_openai_error(error)
        elif provider == "anthropic":
            return cls._classify_anthropic_error(error)
        elif provider == "xai":
            return cls._classify_xai_error(error)
        
        # Fallback classification
        return cls._classify_generic_error(error)
```

### 2. Advanced Retry Manager

```python
# reliability/enhanced_retry.py
# Note: This extends the existing RetryManager in reliability/retry.py

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any
import asyncio
import random
import time
from datetime import datetime, timedelta

from .retry import RetryManager as BaseRetryManager, RetryConfig

@dataclass
class RetryState:
    """Tracks retry state for a request."""
    attempts: int = 0
    total_delay: float = 0.0
    errors: List[Exception] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

@dataclass
class RetryPolicy:
    """Configurable retry policy."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter_factor: float = 0.1
    
    # Retry conditions
    retry_on_timeout: bool = True
    retry_on_rate_limit: bool = True
    retry_on_server_error: bool = True
    retry_on_network_error: bool = True
    
    # Special handling
    respect_retry_after: bool = True
    exponential_backoff: bool = True

class EnhancedRetryManager:
    """Advanced retry manager with policy support.
    
    Extends the existing RetryManager in steer_llm_sdk/reliability/retry.py
    with additional features including:
    - Request-specific retry state tracking
    - Advanced retry policies with per-error-type configuration
    - Retry metrics and observability
    - Integration with circuit breakers
    """
    
    def __init__(self, default_policy: Optional[RetryPolicy] = None):
        self.default_policy = default_policy or RetryPolicy()
        self.retry_states: Dict[str, RetryState] = {}
        # Wrap existing RetryManager for backward compatibility
        self.base_retry_manager = BaseRetryManager()
    
    async def execute_with_retry(
        self,
        func: Callable,
        request_id: str,
        policy: Optional[RetryPolicy] = None
    ) -> Any:
        """Execute function with retry logic."""
        policy = policy or self.default_policy
        state = RetryState()
        self.retry_states[request_id] = state
        
        while state.attempts < policy.max_attempts:
            try:
                # Execute function
                start = time.time()
                result = await func()
                
                # Success - clean up state
                del self.retry_states[request_id]
                return result
                
            except Exception as error:
                state.attempts += 1
                state.errors.append(error)
                
                # Check if we should retry
                if not self._should_retry(error, state, policy):
                    del self.retry_states[request_id]
                    raise
                
                # Calculate delay
                delay = self._calculate_delay(error, state, policy)
                state.total_delay += delay
                
                # Log retry attempt
                await self._log_retry(request_id, state, error, delay)
                
                # Wait before retry
                await asyncio.sleep(delay)
        
        # Max attempts exceeded
        del self.retry_states[request_id]
        raise state.errors[-1]
    
    def _should_retry(
        self,
        error: Exception,
        state: RetryState,
        policy: RetryPolicy
    ) -> bool:
        """Determine if error should be retried."""
        # Check attempt limit
        if state.attempts >= policy.max_attempts:
            return False
        
        # Check error type using ProviderError from steer_llm_sdk/providers/base.py
        if isinstance(error, ProviderError):
            classification = ErrorClassifier.classify_error(
                error.original_error,
                error.provider
            )
            
            # Check category-specific policies
            if classification.category == ErrorCategory.TIMEOUT:
                return policy.retry_on_timeout
            elif classification.category == ErrorCategory.RATE_LIMIT:
                return policy.retry_on_rate_limit
            elif classification.category == ErrorCategory.SERVER_ERROR:
                return policy.retry_on_server_error
            elif classification.category == ErrorCategory.NETWORK:
                return policy.retry_on_network_error
            
            return classification.is_retryable
        
        return False
```

### 3. Streaming Retry Manager

```python
# reliability/streaming_retry.py

from dataclasses import dataclass
from typing import Optional, AsyncGenerator, Callable, Any
import asyncio

@dataclass
class StreamingRetryConfig:
    """Configuration for streaming retries."""
    max_connection_attempts: int = 3
    connection_timeout: float = 30.0
    read_timeout: float = 300.0
    reconnect_on_error: bool = True
    preserve_partial_response: bool = True
    backoff_multiplier: float = 1.5

class StreamingRetryManager:
    """Handles retry logic for streaming connections.
    
    Works in conjunction with EnhancedRetryManager to provide
    streaming-specific retry capabilities.
    """
    
    def __init__(self, retry_manager: EnhancedRetryManager):
        self.retry_manager = retry_manager
        self.stream_states = {}
    
    async def stream_with_retry(
        self,
        stream_func: Callable,
        request_id: str,
        config: StreamingRetryConfig
    ) -> AsyncGenerator[Any, None]:
        """Execute streaming function with retry and recovery."""
        state = StreamState(request_id)
        self.stream_states[request_id] = state
        
        attempt = 0
        while attempt < config.max_connection_attempts:
            try:
                # Attempt connection with timeout
                async with asyncio.timeout(config.connection_timeout):
                    stream = await stream_func()
                
                # Stream chunks with read timeout
                async for chunk in self._read_with_timeout(
                    stream,
                    config.read_timeout,
                    state
                ):
                    yield chunk
                
                # Success - clean up
                del self.stream_states[request_id]
                return
                
            except asyncio.TimeoutError:
                attempt += 1
                if attempt >= config.max_connection_attempts:
                    raise
                
                # Log timeout and retry
                await self._handle_stream_error(
                    "Connection timeout",
                    state,
                    attempt,
                    config
                )
                
            except Exception as error:
                attempt += 1
                if not config.reconnect_on_error or attempt >= config.max_connection_attempts:
                    raise
                
                # Check if error is retryable
                if isinstance(error, ProviderError) and not error.is_retryable:
                    raise
                
                # Handle reconnection
                await self._handle_stream_error(
                    str(error),
                    state,
                    attempt,
                    config
                )
    
    async def _read_with_timeout(
        self,
        stream: AsyncGenerator,
        timeout: float,
        state: StreamState
    ) -> AsyncGenerator[Any, None]:
        """Read from stream with timeout on each chunk."""
        while True:
            try:
                # Wait for next chunk with timeout
                chunk = await asyncio.wait_for(
                    stream.__anext__(),
                    timeout=timeout
                )
                
                # Update state
                state.record_chunk(chunk)
                yield chunk
                
            except asyncio.TimeoutError:
                raise ProviderError(
                    "Read timeout while streaming",
                    provider=state.provider,
                    is_retryable=True
                )
            except StopAsyncIteration:
                break
```

### 4. Circuit Breaker Implementation

```python
# reliability/circuit_breaker.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0
    half_open_requests: int = 3

@dataclass
class CircuitStats:
    """Circuit breaker statistics."""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0

class CircuitBreaker:
    """Circuit breaker for provider connections."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._half_open_permits = 0
        self._state_lock = asyncio.Lock()
    
    async def call(self, func: Callable) -> Any:
        """Execute function through circuit breaker."""
        async with self._state_lock:
            if not self._can_attempt():
                raise ProviderError(
                    f"Circuit breaker {self.name} is OPEN",
                    provider=self.name,
                    is_retryable=True
                )
        
        try:
            # Execute function
            result = await func()
            
            # Record success
            await self._record_success()
            return result
            
        except Exception as error:
            # Record failure
            await self._record_failure()
            raise
    
    async def _can_attempt(self) -> bool:
        """Check if request can be attempted."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self._timeout_expired():
                await self._transition_to_half_open()
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            # Allow limited requests in half-open state
            if self._half_open_permits > 0:
                self._half_open_permits -= 1
                return True
            return False
        
        return False
    
    async def _record_success(self):
        """Record successful call."""
        async with self._state_lock:
            self.stats.success_count += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    await self._transition_to_closed()
    
    async def _record_failure(self):
        """Record failed call."""
        async with self._state_lock:
            self.stats.failure_count += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = datetime.now()
            
            if self.state == CircuitState.CLOSED:
                if self.stats.consecutive_failures >= self.config.failure_threshold:
                    await self._transition_to_open()
            elif self.state == CircuitState.HALF_OPEN:
                await self._transition_to_open()
```

### 5. Stream State Management

```python
# reliability/state.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time
import hashlib

@dataclass
class ChunkMetadata:
    """Metadata for a stream chunk."""
    index: int
    timestamp: float
    size: int
    hash: str
    
@dataclass
class StreamState:
    """Manages state for streaming operations."""
    request_id: str
    provider: str = ""
    model: str = ""
    start_time: float = field(default_factory=time.time)
    chunks: List[ChunkMetadata] = field(default_factory=list)
    partial_response: List[str] = field(default_factory=list)
    total_tokens: int = 0
    last_checkpoint: Optional[int] = None
    
    def record_chunk(self, chunk: str, index: Optional[int] = None):
        """Record a chunk with metadata."""
        if index is None:
            index = len(self.chunks)
        
        metadata = ChunkMetadata(
            index=index,
            timestamp=time.time(),
            size=len(chunk),
            hash=hashlib.md5(chunk.encode()).hexdigest()
        )
        
        self.chunks.append(metadata)
        self.partial_response.append(chunk)
        self.total_tokens += self._estimate_tokens(chunk)
    
    def can_resume(self) -> bool:
        """Check if stream can be resumed from current state."""
        return len(self.chunks) > 0 and self.last_checkpoint is not None
    
    def get_resume_position(self) -> int:
        """Get position to resume streaming from."""
        if self.last_checkpoint is not None:
            return self.last_checkpoint
        return len(self.chunks)
    
    def create_checkpoint(self):
        """Create a checkpoint for current state."""
        self.last_checkpoint = len(self.chunks)
    
    def get_partial_response(self) -> str:
        """Get concatenated partial response."""
        return ''.join(self.partial_response)
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        # Simple estimation: ~4 chars per token
        return len(text) // 4
```

## Integration Points

### 1. Router Integration

```python
# core/routing/router.py updates

class LLMRouter:
    def __init__(self):
        # Existing initialization...
        
        # Reliability components
        # EnhancedRetryManager supersedes the existing RetryManager
        self.retry_manager = EnhancedRetryManager()
        self.streaming_retry = StreamingRetryManager(self.retry_manager)
        self.circuit_breakers = {
            'openai': CircuitBreaker('openai', CircuitBreakerConfig()),
            'anthropic': CircuitBreaker('anthropic', CircuitBreakerConfig()),
            'xai': CircuitBreaker('xai', CircuitBreakerConfig()),
        }
    
    async def generate(self, messages, llm_model_id, params):
        """Generate with retry and circuit breaker."""
        config = get_config(llm_model_id)
        provider_name = config.provider
        
        # Get circuit breaker for provider
        circuit_breaker = self.circuit_breakers.get(provider_name)
        
        async def _generate():
            # Execute through circuit breaker
            if circuit_breaker:
                return await circuit_breaker.call(
                    lambda: self._generate_internal(messages, llm_model_id, params)
                )
            else:
                return await self._generate_internal(messages, llm_model_id, params)
        
        # Execute with retry
        return await self.retry_manager.execute_with_retry(
            _generate,
            request_id=params.get('request_id', 'default'),
            policy=self._get_retry_policy(provider_name)
        )
```

### 2. Client API Updates

```python
# api/client.py updates

class SteerLLMClient:
    async def generate(
        self,
        messages,
        model,
        retry_policy: Optional[RetryPolicy] = None,
        circuit_breaker_enabled: bool = True,
        **kwargs
    ):
        """Generate with reliability options."""
        params = {
            'retry_policy': retry_policy,
            'circuit_breaker_enabled': circuit_breaker_enabled,
            **kwargs
        }
        return await self.router.generate(messages, model, params)
```

## Testing Strategy

### 1. Error Mapping Tests
- Test all known error types for each provider
- Verify correct classification and retry behavior
- Test edge cases and unknown errors

### 2. Retry Behavior Tests
- Test exponential backoff calculation
- Test retry-after header respect
- Test max attempts and timeout

### 3. Circuit Breaker Tests
- Test state transitions
- Test failure threshold triggering
- Test recovery behavior

### 4. Streaming Reliability Tests
- Test connection retry
- Test partial response recovery
- Test timeout handling

### 5. Integration Tests
- End-to-end reliability testing
- Provider-specific failure scenarios
- Performance under failure conditions

## Performance Considerations

1. **Retry Overhead**: < 5ms per retry decision
2. **Circuit Breaker Checks**: < 1ms per check
3. **State Management**: O(1) for state lookups
4. **Memory Usage**: Bounded by max concurrent requests

## Monitoring & Observability

1. **Metrics to Track**:
   - Retry attempts by provider and error type
   - Circuit breaker state changes
   - Stream recovery success rate
   - Error rates and categories

2. **Logging**:
   - Structured logs for all retry attempts
   - Circuit breaker state transitions
   - Stream recovery operations

3. **Alerting Thresholds**:
   - Circuit breaker open for > 5 minutes
   - Retry rate > 10% of requests
   - Stream recovery failure rate > 1%

## Migration Guide

1. **Existing Code**: No breaking changes
2. **New Features**: Opt-in via configuration
3. **Default Behavior**: Conservative retry policy
4. **Testing**: Gradual rollout recommended