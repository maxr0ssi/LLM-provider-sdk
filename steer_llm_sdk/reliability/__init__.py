"""Reliability layer for error handling, retries, and idempotency.

This layer handles:
- Typed error definitions
- Retry logic with exponential backoff
- Idempotency key management
- Token and time budget enforcement
- Enhanced error classification
- Circuit breaker pattern
- Advanced retry policies
"""

from .errors import AgentError, ProviderError, SchemaError, ToolError, TimeoutError
from .retry import RetryManager
from .idempotency import IdempotencyManager
from .budget import clamp_params_to_budget
from .error_classifier import ErrorClassifier, ErrorCategory, ErrorClassification
from .enhanced_retry import EnhancedRetryManager, RetryPolicy, RetryState, RetryMetrics
from .circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitState,
    CircuitStats, CircuitBreakerManager
)
from .streaming_retry import StreamingRetryManager, StreamingRetryConfig
from .state import StreamState, ChunkMetadata, StreamStateManager

__all__ = [
    "AgentError",
    "ProviderError", 
    "SchemaError",
    "ToolError",
    "TimeoutError",
    "RetryManager",
    "IdempotencyManager",
    "clamp_params_to_budget",
    "ErrorClassifier",
    "ErrorCategory",
    "ErrorClassification",
    "EnhancedRetryManager",
    "RetryPolicy",
    "RetryState",
    "RetryMetrics",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircuitStats",
    "CircuitBreakerManager",
    "StreamingRetryManager",
    "StreamingRetryConfig",
    "StreamState",
    "ChunkMetadata",
    "StreamStateManager"
]


