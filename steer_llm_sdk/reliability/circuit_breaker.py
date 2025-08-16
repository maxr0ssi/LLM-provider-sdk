"""
Circuit breaker pattern implementation for provider resilience.

This module implements the circuit breaker pattern to prevent
cascading failures and provide fast failure detection.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any, TypeVar, Tuple
import asyncio
import logging
import time

from ..providers.base import ProviderError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests  
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 2          # Successes to close from half-open
    timeout: float = 60.0              # Seconds before attempting recovery
    half_open_requests: int = 3        # Max requests in half-open state
    
    # Error tracking window
    window_size: float = 60.0          # Time window for failure counting
    
    # Optional callbacks
    on_open: Optional[Callable] = None
    on_close: Optional[Callable] = None
    on_half_open: Optional[Callable] = None


@dataclass 
class CircuitStats:
    """Circuit breaker statistics."""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_state_change: Optional[datetime] = None
    failure_timestamps: list = field(default_factory=list)
    
    def record_success(self):
        """Record a successful call."""
        self.success_count += 1
        self.total_successes += 1
        self.total_requests += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = datetime.now()
        
    def record_failure(self):
        """Record a failed call."""
        now = datetime.now()
        self.failure_count += 1
        self.total_failures += 1
        self.total_requests += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = now
        self.failure_timestamps.append(now)
        
    def get_failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.total_failures / self.total_requests
    
    def get_failures_in_window(self, window_seconds: float) -> int:
        """Count failures within time window."""
        cutoff = datetime.now() - timedelta(seconds=window_seconds)
        # Clean old timestamps
        self.failure_timestamps = [
            ts for ts in self.failure_timestamps if ts > cutoff
        ]
        return len(self.failure_timestamps)


class CircuitBreaker:
    """
    Circuit breaker for provider connections.
    
    Prevents cascading failures by failing fast when a provider
    is experiencing issues.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._half_open_permits = 0
        self._state_lock = asyncio.Lock()
        self._transition_time: Optional[float] = None
        
    async def call(self, func: Callable[[], T]) -> T:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Async function to execute
            
        Returns:
            Result from successful function execution
            
        Raises:
            ProviderError: If circuit is open or half-open with no permits
            Original exception: If function fails
        """
        # Check if we can attempt the call
        can_attempt, error_msg = await self._can_attempt()
        if not can_attempt:
            raise ProviderError(
                error_msg or f"Circuit breaker {self.name} is OPEN",
                provider=self.name,
                status_code=503  # Service Unavailable
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
    
    async def _can_attempt(self) -> tuple[bool, Optional[str]]:
        """Check if request can be attempted.
        
        Returns:
            Tuple of (can_attempt, error_message)
        """
        async with self._state_lock:
            if self.state == CircuitState.CLOSED:
                return True, None
            
            if self.state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._timeout_expired():
                    await self._transition_to_half_open()
                    return True, None
                return False, f"Circuit breaker {self.name} is OPEN"
            
            if self.state == CircuitState.HALF_OPEN:
                # Allow limited requests in half-open state
                if self._half_open_permits > 0:
                    self._half_open_permits -= 1
                    return True, None
                return False, f"Circuit breaker {self.name} is HALF_OPEN with no remaining permits"
            
            return False, f"Circuit breaker {self.name} is in unknown state"
    
    async def _record_success(self):
        """Record successful call."""
        async with self._state_lock:
            self.stats.record_success()
            
            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    await self._transition_to_closed()
            
            # Log success if recovering
            if self.state != CircuitState.CLOSED:
                logger.info(
                    f"Circuit breaker {self.name} recorded success",
                    extra={
                        "circuit_breaker": self.name,
                        "state": self.state.value,
                        "consecutive_successes": self.stats.consecutive_successes
                    }
                )
    
    async def _record_failure(self):
        """Record failed call."""
        async with self._state_lock:
            self.stats.record_failure()
            
            if self.state == CircuitState.CLOSED:
                # Check if we should open based on window
                failures_in_window = self.stats.get_failures_in_window(
                    self.config.window_size
                )
                if failures_in_window >= self.config.failure_threshold:
                    await self._transition_to_open()
            elif self.state == CircuitState.HALF_OPEN:
                # Single failure in half-open goes back to open
                await self._transition_to_open()
            
            # Log failure
            logger.warning(
                f"Circuit breaker {self.name} recorded failure",
                extra={
                    "circuit_breaker": self.name,
                    "state": self.state.value,
                    "consecutive_failures": self.stats.consecutive_failures,
                    "failures_in_window": self.stats.get_failures_in_window(
                        self.config.window_size
                    )
                }
            )
    
    def _timeout_expired(self) -> bool:
        """Check if timeout has expired since opening."""
        if self._transition_time is None:
            return True
        return time.time() - self._transition_time >= self.config.timeout
    
    async def _transition_to_open(self):
        """Transition to OPEN state."""
        previous_state = self.state
        self.state = CircuitState.OPEN
        self._transition_time = time.time()
        self.stats.last_state_change = datetime.now()
        
        logger.error(
            f"Circuit breaker {self.name} opened",
            extra={
                "circuit_breaker": self.name,
                "previous_state": previous_state.value,
                "failure_count": self.stats.failure_count,
                "consecutive_failures": self.stats.consecutive_failures
            }
        )
        
        # Call callback if configured
        if self.config.on_open:
            try:
                await self._call_callback(self.config.on_open)
            except Exception as e:
                logger.error(f"Error in on_open callback: {e}")
    
    async def _transition_to_closed(self):
        """Transition to CLOSED state."""
        previous_state = self.state
        self.state = CircuitState.CLOSED
        self._transition_time = None
        self.stats.last_state_change = datetime.now()
        # Reset consecutive counters
        self.stats.consecutive_failures = 0
        
        logger.info(
            f"Circuit breaker {self.name} closed",
            extra={
                "circuit_breaker": self.name,
                "previous_state": previous_state.value,
                "success_count": self.stats.success_count
            }
        )
        
        # Call callback if configured
        if self.config.on_close:
            try:
                await self._call_callback(self.config.on_close)
            except Exception as e:
                logger.error(f"Error in on_close callback: {e}")
    
    async def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        previous_state = self.state
        self.state = CircuitState.HALF_OPEN
        self._half_open_permits = self.config.half_open_requests
        self.stats.last_state_change = datetime.now()
        # Reset success counter for half-open testing
        self.stats.consecutive_successes = 0
        
        logger.info(
            f"Circuit breaker {self.name} half-open",
            extra={
                "circuit_breaker": self.name,
                "previous_state": previous_state.value,
                "permits": self._half_open_permits
            }
        )
        
        # Call callback if configured
        if self.config.on_half_open:
            try:
                await self._call_callback(self.config.on_half_open)
            except Exception as e:
                logger.error(f"Error in on_half_open callback: {e}")
    
    async def _call_callback(self, callback: Callable):
        """Call callback, handling both sync and async."""
        if asyncio.iscoroutinefunction(callback):
            await callback(self)
        else:
            callback(self)
    
    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state
    
    def get_stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return self.stats
    
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN
    
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.state == CircuitState.HALF_OPEN
    
    async def reset(self):
        """Reset circuit breaker to closed state."""
        async with self._state_lock:
            self.state = CircuitState.CLOSED
            self.stats = CircuitStats()
            self._half_open_permits = 0
            self._transition_time = None
            logger.info(f"Circuit breaker {self.name} reset")


class CircuitBreakerManager:
    """Manages multiple circuit breakers."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
        return self.circuit_breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self.circuit_breakers.get(name)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all circuit breakers."""
        return {
            name: {
                "state": cb.get_state().value,
                "failure_rate": cb.stats.get_failure_rate(),
                "consecutive_failures": cb.stats.consecutive_failures,
                "consecutive_successes": cb.stats.consecutive_successes,
                "total_requests": cb.stats.total_requests
            }
            for name, cb in self.circuit_breakers.items()
        }
    
    async def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            await cb.reset()