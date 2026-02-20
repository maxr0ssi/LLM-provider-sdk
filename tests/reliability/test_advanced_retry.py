"""
Tests for AdvancedRetryManager.

Tests retry logic, policies, and metrics tracking.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import time

from steer_llm_sdk.reliability import (
    AdvancedRetryManager, RetryPolicy, RetryState,
    ErrorCategory
)
from steer_llm_sdk.providers.base import ProviderError


class TestAdvancedRetryManager:
    """Test AdvancedRetryManager functionality."""
    
    @pytest.fixture
    def retry_manager(self):
        """Create retry manager with test policy."""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0,
            backoff_factor=2.0,
            jitter_factor=0.0  # Disable jitter for predictable tests
        )
        return AdvancedRetryManager(default_policy=policy)
    
    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self, retry_manager):
        """Test successful execution without retry."""
        func = AsyncMock(return_value="success")
        
        result = await retry_manager.execute_with_retry(
            func,
            request_id="test-1",
            provider="openai"
        )
        
        assert result == "success"
        assert func.call_count == 1
        assert "test-1" not in retry_manager.retry_states
    
    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self, retry_manager):
        """Test retry on retryable errors."""
        # Create retryable errors
        error1 = ProviderError("Rate limit", provider="openai", status_code=429)
        error1.is_retryable = True
        error1.original_error = Exception("Rate limit")
        error1.error_category = ErrorCategory.RATE_LIMIT
        
        error2 = ProviderError("Server error", provider="openai", status_code=500)
        error2.is_retryable = True
        error2.original_error = Exception("Server error")
        error2.error_category = ErrorCategory.SERVER_ERROR
        
        # Mock function that fails twice then succeeds
        func = AsyncMock(side_effect=[error1, error2, "success"])
        
        result = await retry_manager.execute_with_retry(
            func,
            request_id="test-2",
            provider="openai"
        )
        
        assert result == "success"
        assert func.call_count == 3
        
        # Check metrics
        metrics = retry_manager.get_metrics()
        assert metrics.retry_successes.get("openai") == 1
        assert len(metrics.retry_attempts) > 0
    
    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self, retry_manager):
        """Test no retry on non-retryable errors."""
        error = ProviderError("Authentication failed", provider="openai", status_code=401)
        error.is_retryable = False
        
        func = AsyncMock(side_effect=error)
        
        with pytest.raises(ProviderError) as exc_info:
            await retry_manager.execute_with_retry(
                func,
                request_id="test-3",
                provider="openai"
            )
        
        assert func.call_count == 1
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self, retry_manager):
        """Test max attempts exceeded."""
        error = ProviderError("Server error", provider="openai", status_code=500)
        error.is_retryable = True
        error.original_error = Exception("Server error") 
        error.error_category = ErrorCategory.SERVER_ERROR
        
        func = AsyncMock(side_effect=error)
        
        with pytest.raises(ProviderError):
            await retry_manager.execute_with_retry(
                func,
                request_id="test-4",
                provider="openai"
            )
        
        assert func.call_count == 3  # max_attempts = 3
        
        # Check failure metrics
        metrics = retry_manager.get_metrics()
        assert metrics.retry_failures.get("openai") == 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, retry_manager):
        """Test exponential backoff calculation."""
        error = ProviderError("Server error", provider="openai", status_code=500)
        error.is_retryable = True
        error.original_error = Exception("Server error")
        error.error_category = ErrorCategory.SERVER_ERROR
        
        func = AsyncMock(side_effect=error)
        
        start_time = time.time()
        
        with pytest.raises(ProviderError):
            await retry_manager.execute_with_retry(
                func,
                request_id="test-5",
                provider="openai"
            )
        
        elapsed_time = time.time() - start_time
        
        # Expected delays: 0.1, 0.2 (0.1 * 2)
        # Total expected: ~0.3 seconds (plus some overhead)
        assert 0.25 < elapsed_time < 0.5
    
    @pytest.mark.asyncio
    async def test_respect_retry_after(self, retry_manager):
        """Test respecting retry-after header."""
        error = ProviderError("Rate limit", provider="openai", status_code=429)
        error.is_retryable = True
        error.retry_after = 0.2  # 200ms retry after
        error.original_error = Exception("Rate limit")
        error.error_category = ErrorCategory.RATE_LIMIT
        
        func = AsyncMock(side_effect=[error, "success"])
        
        start_time = time.time()
        
        result = await retry_manager.execute_with_retry(
            func,
            request_id="test-6",
            provider="openai"
        )
        
        elapsed_time = time.time() - start_time
        
        assert result == "success"
        # Should wait at least 200ms
        assert elapsed_time >= 0.2
    
    @pytest.mark.asyncio
    async def test_custom_retry_policy(self, retry_manager):
        """Test custom retry policy."""
        custom_policy = RetryPolicy(
            max_attempts=2,
            initial_delay=0.05,
            retry_on_server_error=False
        )
        
        error = ProviderError("Server error", provider="openai", status_code=500)
        error.is_retryable = True
        error.original_error = Exception("Server error")
        error.error_category = ErrorCategory.SERVER_ERROR
        
        func = AsyncMock(side_effect=error)
        
        with pytest.raises(ProviderError):
            await retry_manager.execute_with_retry(
                func,
                request_id="test-7",
                provider="openai",
                policy=custom_policy
            )
        
        # Should not retry due to custom policy
        assert func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_state_tracking(self, retry_manager):
        """Test retry state tracking during execution."""
        error = ProviderError("Server error", provider="openai", status_code=500)
        error.is_retryable = True
        error.original_error = Exception("Server error")
        error.error_category = ErrorCategory.SERVER_ERROR
        
        call_count = 0
        
        async def func_with_state_check():
            nonlocal call_count
            call_count += 1
            
            # Check state exists during retry
            state = retry_manager.get_retry_state("test-8")
            if call_count < 3:
                assert state is not None
                assert state.attempts == call_count - 1
                raise error
            return "success"
        
        result = await retry_manager.execute_with_retry(
            func_with_state_check,
            request_id="test-8",
            provider="openai"
        )
        
        assert result == "success"
        # State should be cleaned up after success
        assert retry_manager.get_retry_state("test-8") is None
    
    @pytest.mark.asyncio
    async def test_max_total_delay(self, retry_manager):
        """Test max total delay limit."""
        policy = RetryPolicy(
            max_attempts=10,  # High attempt count
            initial_delay=1.0,
            max_total_delay=0.5  # But low total delay limit
        )
        
        error = ProviderError("Server error", provider="openai", status_code=500)
        error.is_retryable = True
        error.original_error = Exception("Server error")
        error.error_category = ErrorCategory.SERVER_ERROR
        
        func = AsyncMock(side_effect=error)
        
        start_time = time.time()
        
        with pytest.raises(ProviderError):
            await retry_manager.execute_with_retry(
                func,
                request_id="test-9",
                provider="openai",
                policy=policy
            )
        
        elapsed_time = time.time() - start_time
        
        # Should stop before reaching max attempts due to total delay limit
        assert func.call_count < 10
        assert elapsed_time < 1.0
    
    def test_metrics_tracking(self, retry_manager):
        """Test metrics tracking functionality."""
        metrics = retry_manager.get_metrics()
        
        # Initial state
        assert metrics.retry_attempts == {}
        assert metrics.retry_successes == {}
        assert metrics.retry_failures == {}
        assert metrics.total_retry_delay == 0.0
        
        # Reset metrics
        retry_manager.reset_metrics()
        metrics = retry_manager.get_metrics()
        assert metrics.retry_attempts == {}


class TestRetryPolicy:
    """Test RetryPolicy configuration."""
    
    def test_default_policy(self):
        """Test default retry policy."""
        policy = RetryPolicy()
        
        assert policy.max_attempts == 3
        assert policy.initial_delay == 1.0
        assert policy.retry_on_timeout is True
        assert policy.retry_on_rate_limit is True
        assert policy.retry_on_server_error is True
        assert policy.retry_on_network_error is True
    
    def test_should_retry_category(self):
        """Test category-based retry decisions."""
        policy = RetryPolicy(
            retry_on_timeout=False,
            retry_on_rate_limit=True
        )
        
        assert policy.should_retry_category(ErrorCategory.RATE_LIMIT) is True
        assert policy.should_retry_category(ErrorCategory.TIMEOUT) is False
        assert policy.should_retry_category(ErrorCategory.AUTHENTICATION) is False