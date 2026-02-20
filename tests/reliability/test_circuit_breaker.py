"""
Tests for Circuit Breaker implementation.

Tests state transitions, failure thresholds, and recovery behavior.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import time
from datetime import datetime, timedelta

from steer_llm_sdk.reliability import (
    CircuitBreaker, CircuitBreakerConfig, CircuitState,
    CircuitBreakerManager
)
from steer_llm_sdk.providers.base import ProviderError


class TestCircuitBreaker:
    """Test CircuitBreaker functionality."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker with test config."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=0.5,  # 500ms for faster tests
            window_size=60.0
        )
        return CircuitBreaker("test-provider", config)
    
    @pytest.mark.asyncio
    async def test_initial_state(self, circuit_breaker):
        """Test circuit breaker starts in closed state."""
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.is_closed()
        assert not circuit_breaker.is_open()
        assert not circuit_breaker.is_half_open()
    
    @pytest.mark.asyncio
    async def test_successful_calls_in_closed_state(self, circuit_breaker):
        """Test successful calls don't open circuit."""
        func = AsyncMock(return_value="success")
        
        # Make multiple successful calls
        for _ in range(5):
            result = await circuit_breaker.call(func)
            assert result == "success"
        
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.stats.success_count == 5
        assert circuit_breaker.stats.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_opens_on_failure_threshold(self, circuit_breaker):
        """Test circuit opens after failure threshold."""
        func = AsyncMock(side_effect=Exception("Test error"))
        
        # First 2 failures - circuit stays closed
        for i in range(2):
            with pytest.raises(Exception):
                await circuit_breaker.call(func)
            assert circuit_breaker.get_state() == CircuitState.CLOSED
        
        # Third failure - circuit opens
        with pytest.raises(Exception):
            await circuit_breaker.call(func)
        
        assert circuit_breaker.get_state() == CircuitState.OPEN
        assert circuit_breaker.is_open()
        assert circuit_breaker.stats.consecutive_failures == 3
    
    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self, circuit_breaker):
        """Test open circuit rejects calls immediately."""
        # Force circuit to open
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker._transition_time = time.time()
        
        func = AsyncMock(return_value="should not be called")
        
        with pytest.raises(ProviderError) as exc_info:
            await circuit_breaker.call(func)
        
        assert "Circuit breaker test-provider is OPEN" in str(exc_info.value)
        assert func.call_count == 0  # Function not called
    
    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, circuit_breaker):
        """Test circuit transitions to half-open after timeout."""
        # Force circuit to open
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker._transition_time = time.time() - 1.0  # 1 second ago
        
        func = AsyncMock(return_value="success")
        
        # First call should transition to half-open and succeed
        result = await circuit_breaker.call(func)
        assert result == "success"
        assert circuit_breaker.get_state() == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success(self, circuit_breaker):
        """Test circuit closes after success threshold in half-open."""
        # Set to half-open state
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker._half_open_permits = 3
        
        func = AsyncMock(return_value="success")
        
        # First success
        await circuit_breaker.call(func)
        assert circuit_breaker.get_state() == CircuitState.HALF_OPEN
        
        # Second success - should close
        await circuit_breaker.call(func)
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.stats.consecutive_successes == 2
    
    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self, circuit_breaker):
        """Test circuit reopens on failure in half-open state."""
        # Set to half-open state
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker._half_open_permits = 3
        
        func = AsyncMock(side_effect=Exception("Test error"))
        
        # Single failure should reopen
        with pytest.raises(Exception):
            await circuit_breaker.call(func)
        
        assert circuit_breaker.get_state() == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_half_open_permits_limit(self, circuit_breaker):
        """Test half-open state permits are limited."""
        # Create a circuit breaker with higher success threshold to test permit limits
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=5,  # Higher than permits to test permit exhaustion
            timeout=0.5,
            half_open_requests=2  # Only 2 permits
        )
        cb = CircuitBreaker("test-permits", config)
        
        # Set to half-open state
        cb.state = CircuitState.HALF_OPEN
        cb._half_open_permits = 2
        
        func = AsyncMock(return_value="success")
        
        # First two calls succeed
        await cb.call(func)
        await cb.call(func)
        
        # Third call should be rejected (no permits left)
        with pytest.raises(ProviderError) as exc_info:
            await cb.call(func)
        
        assert "no remaining permits" in str(exc_info.value)
        assert func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_failure_window_tracking(self, circuit_breaker):
        """Test failures are tracked within time window."""
        func = AsyncMock(side_effect=Exception("Test error"))
        
        # Add old failures (outside window)
        old_time = datetime.now() - timedelta(seconds=120)
        circuit_breaker.stats.failure_timestamps = [old_time, old_time]
        
        # Add new failures
        for _ in range(2):
            with pytest.raises(Exception):
                await circuit_breaker.call(func)
        
        # Old failures should be cleaned, circuit still closed
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert len(circuit_breaker.stats.failure_timestamps) == 2
        
        # One more failure opens circuit
        with pytest.raises(Exception):
            await circuit_breaker.call(func)
        
        assert circuit_breaker.get_state() == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_reset_functionality(self, circuit_breaker):
        """Test circuit breaker reset."""
        # Put circuit in open state with some stats
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.stats.failure_count = 10
        circuit_breaker.stats.success_count = 5
        
        await circuit_breaker.reset()
        
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.stats.failure_count == 0
        assert circuit_breaker.stats.success_count == 0
    
    def test_failure_rate_calculation(self, circuit_breaker):
        """Test failure rate calculation."""
        stats = circuit_breaker.stats
        
        # No requests
        assert stats.get_failure_rate() == 0.0
        
        # Some failures and successes
        stats.total_failures = 3
        stats.total_successes = 7
        stats.total_requests = 10
        
        assert stats.get_failure_rate() == 0.3


class TestCircuitBreakerManager:
    """Test CircuitBreakerManager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create circuit breaker manager."""
        return CircuitBreakerManager()
    
    def test_get_or_create(self, manager):
        """Test get_or_create functionality."""
        # Create new circuit breaker
        cb1 = manager.get_or_create("provider1")
        assert cb1 is not None
        assert cb1.name == "provider1"
        
        # Get existing circuit breaker
        cb2 = manager.get_or_create("provider1")
        assert cb2 is cb1  # Same instance
        
        # Create with custom config
        config = CircuitBreakerConfig(failure_threshold=5)
        cb3 = manager.get_or_create("provider2", config)
        assert cb3.config.failure_threshold == 5
    
    def test_get_nonexistent(self, manager):
        """Test getting non-existent circuit breaker."""
        cb = manager.get("nonexistent")
        assert cb is None
    
    def test_get_all_stats(self, manager):
        """Test getting stats for all circuit breakers."""
        # Create some circuit breakers
        cb1 = manager.get_or_create("provider1")
        cb2 = manager.get_or_create("provider2")
        
        # Add some stats
        cb1.stats.total_requests = 100
        cb1.stats.total_failures = 10
        cb2.state = CircuitState.OPEN
        
        stats = manager.get_all_stats()
        
        assert "provider1" in stats
        assert stats["provider1"]["state"] == "closed"
        assert stats["provider1"]["total_requests"] == 100
        assert stats["provider1"]["failure_rate"] == 0.1
        
        assert "provider2" in stats
        assert stats["provider2"]["state"] == "open"
    
    @pytest.mark.asyncio
    async def test_reset_all(self, manager):
        """Test resetting all circuit breakers."""
        # Create and modify circuit breakers
        cb1 = manager.get_or_create("provider1")
        cb2 = manager.get_or_create("provider2")
        
        cb1.state = CircuitState.OPEN
        cb2.state = CircuitState.HALF_OPEN
        
        await manager.reset_all()
        
        assert cb1.get_state() == CircuitState.CLOSED
        assert cb2.get_state() == CircuitState.CLOSED


class TestCircuitBreakerCallbacks:
    """Test circuit breaker callback functionality."""
    
    @pytest.mark.asyncio
    async def test_on_open_callback(self):
        """Test on_open callback is called."""
        callback_called = False
        
        def on_open(cb):
            nonlocal callback_called
            callback_called = True
            assert cb.name == "test"
        
        config = CircuitBreakerConfig(
            failure_threshold=1,
            on_open=on_open
        )
        cb = CircuitBreaker("test", config)
        
        func = AsyncMock(side_effect=Exception("Test"))
        
        with pytest.raises(Exception):
            await cb.call(func)
        
        assert callback_called
        assert cb.get_state() == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_async_callback(self):
        """Test async callbacks work correctly."""
        callback_called = False
        
        async def on_close(cb):
            nonlocal callback_called
            callback_called = True
            await asyncio.sleep(0.01)  # Simulate async work
        
        config = CircuitBreakerConfig(
            success_threshold=1,
            on_close=on_close
        )
        cb = CircuitBreaker("test", config)
        
        # Transition from half-open to closed
        cb.state = CircuitState.HALF_OPEN
        cb._half_open_permits = 1
        
        func = AsyncMock(return_value="success")
        await cb.call(func)
        
        assert callback_called
        assert cb.get_state() == CircuitState.CLOSED