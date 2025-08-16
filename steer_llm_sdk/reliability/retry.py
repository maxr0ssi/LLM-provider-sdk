from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Iterable, Type, Optional

from ..providers.base import ProviderError


@dataclass
class RetryConfig:
    max_attempts: int = 2
    backoff_factor: float = 2.0
    retryable_errors: Iterable[Type[Exception]] = ()
    initial_delay: float = 0.25
    max_delay: float = 60.0


class RetryManager:
    """
    Manages retry logic for provider operations.
    
    This class handles:
    - Provider-aware retry decisions
    - Exponential backoff with jitter
    - Respect for Retry-After headers
    - Maximum delay caps
    """
    
    async def execute_with_retry(self, func: Callable, config: RetryConfig):
        """
        Execute a function with retry logic.
        
        Args:
            func: Async function to execute
            config: Retry configuration
            
        Returns:
            Result from successful function execution
            
        Raises:
            The last exception if all retries are exhausted
        """
        attempt = 0
        delay = config.initial_delay
        
        while True:
            try:
                return await func()
            except Exception as e:  # noqa: BLE001
                attempt += 1
                
                # Check if we should retry
                should_retry = self._should_retry(e, attempt, config)
                if not should_retry:
                    raise
                
                # Calculate delay
                retry_delay = self._calculate_delay(e, delay, config)
                
                # Wait before retry
                await asyncio.sleep(retry_delay)
                
                # Update delay for next iteration
                delay = min(delay * config.backoff_factor, config.max_delay)
    
    def _should_retry(self, error: Exception, attempt: int, config: RetryConfig) -> bool:
        """Determine if an error should be retried."""
        # Check max attempts
        if attempt >= config.max_attempts:
            return False
        
        # Check if it's a ProviderError with retryable flag
        if isinstance(error, ProviderError):
            return error.is_retryable
        
        # Fall back to checking error types
        return any(isinstance(error, error_type) for error_type in config.retryable_errors)
    
    def _calculate_delay(self, error: Exception, base_delay: float, config: RetryConfig) -> float:
        """Calculate retry delay, respecting Retry-After if present."""
        # Check for explicit retry-after
        if isinstance(error, ProviderError) and error.retry_after:
            return min(error.retry_after, config.max_delay)
        
        # Add jitter to prevent thundering herd
        import random
        jitter = random.uniform(0, 0.1 * base_delay)
        
        return min(base_delay + jitter, config.max_delay)


