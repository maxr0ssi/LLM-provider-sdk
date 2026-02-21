"""
Tests for StreamingRetryManager.

Tests streaming-specific retry logic and recovery.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncGenerator

from steer_llm_sdk.reliability import (
    StreamingRetryManager, StreamingRetryConfig,
    AdvancedRetryManager, StreamState
)
from steer_llm_sdk.providers.base import ProviderError


class TestStreamingRetryManager:
    """Test StreamingRetryManager functionality."""
    
    @pytest.fixture
    def retry_manager(self):
        """Create retry manager."""
        return AdvancedRetryManager()
    
    @pytest.fixture
    def streaming_retry(self, retry_manager):
        """Create streaming retry manager."""
        return StreamingRetryManager(retry_manager)
    
    async def create_mock_stream(self, chunks, error_after=None):
        """Create a mock async generator."""
        for i, chunk in enumerate(chunks):
            if error_after is not None and i == error_after:
                raise Exception("Stream error")
            yield chunk
    
    @pytest.mark.asyncio
    async def test_successful_stream_no_retry(self, streaming_retry):
        """Test successful streaming without retry."""
        chunks = ["chunk1", "chunk2", "chunk3"]
        
        async def stream_func():
            return self.create_mock_stream(chunks)
        
        config = StreamingRetryConfig(max_connection_attempts=3)
        
        received_chunks = []
        async for chunk in streaming_retry.stream_with_retry(
            stream_func,
            request_id="test-1",
            provider="openai",
            config=config
        ):
            received_chunks.append(chunk)
        
        assert received_chunks == chunks
        assert "test-1" not in streaming_retry.stream_states
    
    @pytest.mark.asyncio
    async def test_stream_connection_timeout(self, streaming_retry):
        """Test stream connection timeout handling."""
        async def slow_stream_func():
            await asyncio.sleep(2.0)  # Longer than timeout
            return self.create_mock_stream(["chunk"])
        
        config = StreamingRetryConfig(
            connection_timeout=0.1,
            max_connection_attempts=2
        )
        
        with pytest.raises(ProviderError) as exc_info:
            async for _ in streaming_retry.stream_with_retry(
                slow_stream_func,
                request_id="test-2",
                provider="openai",
                config=config
            ):
                pass
        
        assert "connection timeout" in str(exc_info.value).lower()
        assert exc_info.value.status_code == 504
    
    @pytest.mark.asyncio
    async def test_stream_read_timeout(self, streaming_retry):
        """Test stream read timeout handling."""
        async def slow_chunk_stream():
            yield "chunk1"
            # This will block forever, causing repeated timeouts
            while True:
                await asyncio.sleep(10.0)  # Much longer than read timeout
        
        async def stream_func():
            return slow_chunk_stream()
        
        config = StreamingRetryConfig(
            read_timeout=0.1,
            max_connection_attempts=1
        )
        
        received_chunks = []
        with pytest.raises(ProviderError) as exc_info:
            async for chunk in streaming_retry.stream_with_retry(
                stream_func,
                request_id="test-3",  
                provider="openai",
                config=config
            ):
                received_chunks.append(chunk)
        
        assert len(received_chunks) == 1  # Got first chunk
        assert "timeout" in str(exc_info.value).lower()
        assert exc_info.value.status_code == 504
    
    @pytest.mark.asyncio
    async def test_stream_retry_on_error(self, streaming_retry):
        """Test stream retry on recoverable error."""
        attempt = 0
        
        async def flaky_stream_func():
            nonlocal attempt
            attempt += 1
            
            if attempt == 1:
                # First attempt fails after 2 chunks
                async def stream():
                    yield "chunk1"
                    yield "chunk2"
                    raise Exception("Connection error")
                return stream()
            else:
                # Second attempt succeeds
                async def stream():
                    yield "chunk3"
                    yield "chunk4"
                return stream()
        
        config = StreamingRetryConfig(
            max_connection_attempts=2,
            reconnect_on_error=True
        )
        
        received_chunks = []
        async for chunk in streaming_retry.stream_with_retry(
            flaky_stream_func,
            request_id="test-4",
            provider="openai",
            config=config
        ):
            received_chunks.append(chunk)
        
        # Should get all chunks (no deduplication in this test)
        assert received_chunks == ["chunk1", "chunk2", "chunk3", "chunk4"]
        assert attempt == 2
    
    @pytest.mark.asyncio
    async def test_stream_state_tracking(self, streaming_retry):
        """Test stream state is tracked correctly."""
        chunks = ["chunk1", "chunk2", "chunk3"]
        
        async def stream_func():
            return self.create_mock_stream(chunks)
        
        config = StreamingRetryConfig()
        request_id = "test-5"
        
        # Check state during streaming
        received_count = 0
        async for chunk in streaming_retry.stream_with_retry(
            stream_func,
            request_id=request_id,
            provider="openai",
            config=config
        ):
            received_count += 1
            
            # Check state exists during streaming
            state = streaming_retry.get_stream_state(request_id)
            if received_count < len(chunks):
                assert state is not None
                assert len(state.chunks) == received_count
                assert state.provider == "openai"
        
        # State should be cleaned up after completion
        assert streaming_retry.get_stream_state(request_id) is None
    
    @pytest.mark.asyncio
    async def test_partial_response_tracking(self, streaming_retry):
        """Test partial response is tracked."""
        async def failing_stream():
            yield "Hello "
            yield "World"
            raise Exception("Stream interrupted")
        
        async def stream_func():
            return failing_stream()
        
        config = StreamingRetryConfig(
            max_connection_attempts=1  # No retry
        )
        
        request_id = "test-6"
        
        with pytest.raises(Exception):
            async for _ in streaming_retry.stream_with_retry(
                stream_func,
                request_id=request_id,
                provider="openai",
                config=config
            ):
                pass
        
        # Check partial response was captured
        assert streaming_retry.has_partial_response(request_id)
        partial = streaming_retry.get_partial_response(request_id)
        assert partial == "Hello World"
    
    @pytest.mark.asyncio
    async def test_checkpoint_creation(self, streaming_retry):
        """Test checkpoint creation during streaming."""
        # Create many chunks to trigger checkpoint
        chunks = [f"chunk{i}" for i in range(25)]
        
        async def stream_func():
            return self.create_mock_stream(chunks)
        
        config = StreamingRetryConfig()
        request_id = "test-7"
        
        received_chunks = []
        async for chunk in streaming_retry.stream_with_retry(
            stream_func,
            request_id=request_id,
            provider="openai",
            config=config
        ):
            received_chunks.append(chunk)
            
            # Check if checkpoint was created
            if len(received_chunks) == 10:
                state = streaming_retry.get_stream_state(request_id)
                if state:
                    assert state.last_checkpoint is not None
        
        assert len(received_chunks) == 25
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, streaming_retry):
        """Test exponential backoff between retries."""
        attempt = 0
        
        async def always_fail_stream():
            nonlocal attempt
            attempt += 1
            raise Exception("Connection error")
        
        config = StreamingRetryConfig(
            max_connection_attempts=3,
            initial_backoff=0.1,
            backoff_multiplier=2.0
        )
        
        import time
        start_time = time.time()
        
        with pytest.raises(Exception):
            async for _ in streaming_retry.stream_with_retry(
                always_fail_stream,
                request_id="test-8",
                provider="openai",
                config=config
            ):
                pass
        
        elapsed = time.time() - start_time
        
        # Expected delays: 0.1, 0.2 = 0.3 total (plus overhead)
        assert attempt == 3
        assert 0.25 < elapsed < 0.8  # Allow more overhead for async operations
    
    @pytest.mark.asyncio
    async def test_non_retryable_error(self, streaming_retry):
        """Test non-retryable errors stop retry."""
        async def auth_error_stream():
            yield "chunk1"
            error = ProviderError("Auth failed", provider="openai", status_code=401)
            error.is_retryable = False
            raise error
        
        async def stream_func():
            return auth_error_stream()
        
        config = StreamingRetryConfig(
            max_connection_attempts=3,
            reconnect_on_error=True
        )
        
        received = []
        with pytest.raises(ProviderError) as exc_info:
            async for chunk in streaming_retry.stream_with_retry(
                stream_func,
                request_id="test-9",
                provider="openai",
                config=config
            ):
                received.append(chunk)
        
        assert len(received) == 1
        assert exc_info.value.status_code == 401
        # Should not retry on non-retryable error


class TestStreamingRetryConfig:
    """Test StreamingRetryConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = StreamingRetryConfig()
        
        assert config.max_connection_attempts == 3
        assert config.connection_timeout == 30.0
        assert config.read_timeout == 300.0
        assert config.reconnect_on_error is True
        assert config.preserve_partial_response is True
        
    def test_custom_config(self):
        """Test custom configuration."""
        config = StreamingRetryConfig(
            max_connection_attempts=5,
            connection_timeout=60.0,
            reconnect_on_error=False
        )
        
        assert config.max_connection_attempts == 5
        assert config.connection_timeout == 60.0
        assert config.reconnect_on_error is False