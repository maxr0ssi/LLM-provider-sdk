"""
Enhanced retry manager with advanced features.

This module extends the basic RetryManager with:
- Request-specific retry state tracking
- Advanced retry policies with per-error-type configuration
- Retry metrics and observability
- Integration with circuit breakers
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from ..providers.base import ProviderError
from .error_classifier import ErrorCategory, ErrorClassifier
from .retry import RetryConfig
from .retry import RetryManager as BaseRetryManager

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryState:
    """Tracks retry state for a request."""
    attempts: int = 0
    total_delay: float = 0.0
    errors: List[Exception] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    error_categories: List[ErrorCategory] = field(default_factory=list)
    
    def add_attempt(self, error: Exception, delay: float, category: ErrorCategory):
        """Record a retry attempt."""
        self.attempts += 1
        self.errors.append(error)
        self.total_delay += delay
        self.error_categories.append(category)
    
    def get_duration(self) -> float:
        """Get total duration since start."""
        return time.time() - self.start_time
    
    def get_last_error(self) -> Optional[Exception]:
        """Get the most recent error."""
        return self.errors[-1] if self.errors else None


@dataclass
class RetryPolicy:
    """Configurable retry policy with advanced options."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter_factor: float = 0.1
    
    # Retry conditions by error category
    retry_on_timeout: bool = True
    retry_on_rate_limit: bool = True
    retry_on_server_error: bool = True
    retry_on_network_error: bool = True
    
    # Special handling
    respect_retry_after: bool = True
    exponential_backoff: bool = True
    max_total_delay: float = 300.0  # 5 minutes max total retry time
    
    def should_retry_category(self, category: ErrorCategory) -> bool:
        """Check if error category should be retried."""
        category_map = {
            ErrorCategory.TIMEOUT: self.retry_on_timeout,
            ErrorCategory.RATE_LIMIT: self.retry_on_rate_limit,
            ErrorCategory.SERVER_ERROR: self.retry_on_server_error,
            ErrorCategory.NETWORK: self.retry_on_network_error,
        }
        return category_map.get(category, False)


class RetryMetrics:
    """Tracks retry metrics for observability."""
    
    def __init__(self):
        self.retry_attempts: Dict[str, int] = {}
        self.retry_successes: Dict[str, int] = {}
        self.retry_failures: Dict[str, int] = {}
        self.error_counts: Dict[ErrorCategory, int] = {}
        self.total_retry_delay: float = 0.0
        
    def record_attempt(self, provider: str, category: ErrorCategory):
        """Record a retry attempt."""
        key = f"{provider}:{category.value}"
        self.retry_attempts[key] = self.retry_attempts.get(key, 0) + 1
        self.error_counts[category] = self.error_counts.get(category, 0) + 1
    
    def record_success(self, provider: str, attempts: int):
        """Record successful retry."""
        self.retry_successes[provider] = self.retry_successes.get(provider, 0) + 1
    
    def record_failure(self, provider: str, attempts: int):
        """Record failed retry."""
        self.retry_failures[provider] = self.retry_failures.get(provider, 0) + 1
    
    def add_delay(self, delay: float):
        """Add to total retry delay."""
        self.total_retry_delay += delay
    
    def get_success_rate(self, provider: str) -> float:
        """Calculate retry success rate for provider."""
        successes = self.retry_successes.get(provider, 0)
        failures = self.retry_failures.get(provider, 0)
        total = successes + failures
        return successes / total if total > 0 else 0.0


class EnhancedRetryManager:
    """
    Advanced retry manager with policy support.
    
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
        self.metrics = RetryMetrics()
        
    async def execute_with_retry(
        self,
        func: Callable[[], T],
        request_id: str,
        provider: str = "unknown",
        policy: Optional[RetryPolicy] = None
    ) -> T:
        """
        Execute function with retry logic.
        
        Args:
            func: Async function to execute
            request_id: Unique request identifier
            provider: Provider name for metrics
            policy: Optional custom retry policy
            
        Returns:
            Result from successful function execution
            
        Raises:
            The last exception if all retries are exhausted
        """
        policy = policy or self.default_policy
        state = RetryState()
        self.retry_states[request_id] = state
        
        while state.attempts < policy.max_attempts:
            try:
                # Execute function
                start = time.time()
                result = await func()
                
                # Success - clean up state and record metrics
                if state.attempts > 0:
                    self.metrics.record_success(provider, state.attempts)
                    logger.info(
                        f"Request {request_id} succeeded after {state.attempts} retries",
                        extra={
                            "request_id": request_id,
                            "provider": provider,
                            "attempts": state.attempts,
                            "total_delay": state.total_delay
                        }
                    )
                
                del self.retry_states[request_id]
                return result
                
            except Exception as error:
                # Classify the error
                classification = self._classify_error(error, provider)
                
                # Check if we should retry
                if not self._should_retry(error, state, policy, classification):
                    del self.retry_states[request_id]
                    self.metrics.record_failure(provider, state.attempts + 1)
                    raise
                
                # Calculate delay
                delay = self._calculate_delay(error, state, policy, classification)
                
                # Check total delay limit
                if state.total_delay + delay > policy.max_total_delay:
                    logger.warning(
                        f"Request {request_id} exceeded max total delay",
                        extra={"request_id": request_id, "total_delay": state.total_delay}
                    )
                    del self.retry_states[request_id]
                    self.metrics.record_failure(provider, state.attempts + 1)
                    raise
                
                # Record attempt
                state.add_attempt(error, delay, classification.category)
                self.metrics.record_attempt(provider, classification.category)
                self.metrics.add_delay(delay)
                
                # Log retry attempt
                await self._log_retry(request_id, state, error, delay, provider)
                
                # Wait before retry
                await asyncio.sleep(delay)
        
        # Max attempts exceeded
        last_error = state.get_last_error() or Exception("Max retry attempts exceeded")
        del self.retry_states[request_id]
        self.metrics.record_failure(provider, state.attempts)
        raise last_error
    
    def _classify_error(self, error: Exception, provider: str) -> Any:
        """Classify error using ErrorClassifier."""
        if isinstance(error, ProviderError):
            return ErrorClassifier.classify_error(
                error.original_error if hasattr(error, 'original_error') else error,
                provider
            )
        return ErrorClassifier.classify_error(error, provider)
    
    def _should_retry(
        self,
        error: Exception,
        state: RetryState,
        policy: RetryPolicy,
        classification: Any
    ) -> bool:
        """Determine if error should be retried."""
        # Check attempt limit (attempts is 0-based, so we check before incrementing)
        if state.attempts >= policy.max_attempts - 1:
            return False
        
        # Check explicit retryable flag first (short-circuit on explicit retryable)
        if isinstance(error, ProviderError) and hasattr(error, 'is_retryable') and error.is_retryable:
            return True  # Honor explicit is_retryable=True
        
        # Check if error is retryable
        if not classification.is_retryable:
            return False
        
        # Check category-specific policies
        if not policy.should_retry_category(classification.category):
            return False
        
        # Additional checks for ProviderError
        if isinstance(error, ProviderError):
            # Respect the is_retryable flag
            if hasattr(error, 'is_retryable') and not error.is_retryable:
                return False
        
        return True
    
    def _calculate_delay(
        self,
        error: Exception,
        state: RetryState,
        policy: RetryPolicy,
        classification: Any
    ) -> float:
        """Calculate retry delay with backoff and jitter."""
        # Check for retry_after directly on ProviderError first
        if isinstance(error, ProviderError) and hasattr(error, 'retry_after') and error.retry_after and policy.respect_retry_after:
            base_delay = error.retry_after
        # Use suggested delay from classification if available
        elif classification.suggested_delay and policy.respect_retry_after:
            base_delay = classification.suggested_delay
        else:
            # Calculate exponential backoff
            if policy.exponential_backoff:
                base_delay = policy.initial_delay * (policy.backoff_factor ** state.attempts)
            else:
                base_delay = policy.initial_delay
        
        # Cap at max delay
        base_delay = min(base_delay, policy.max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(-policy.jitter_factor, policy.jitter_factor) * base_delay
        final_delay = max(0.1, base_delay + jitter)  # Ensure minimum 100ms delay
        
        return final_delay
    
    async def _log_retry(
        self,
        request_id: str,
        state: RetryState,
        error: Exception,
        delay: float,
        provider: str
    ):
        """Log retry attempt with context."""
        error_type = type(error).__name__
        error_msg = str(error)[:200]  # Truncate long error messages
        
        logger.warning(
            f"Retrying request {request_id} after {error_type}",
            extra={
                "request_id": request_id,
                "provider": provider,
                "attempt": state.attempts + 1,
                "error_type": error_type,
                "error_message": error_msg,
                "delay": delay,
                "total_delay": state.total_delay,
                "error_category": state.error_categories[-1].value if state.error_categories else "unknown"
            }
        )
    
    def get_retry_state(self, request_id: str) -> Optional[RetryState]:
        """Get current retry state for a request."""
        return self.retry_states.get(request_id)
    
    def get_metrics(self) -> RetryMetrics:
        """Get retry metrics."""
        return self.metrics
    
    def reset_metrics(self):
        """Reset metrics."""
        self.metrics = RetryMetrics()
