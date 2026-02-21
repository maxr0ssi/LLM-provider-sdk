"""
Integration tests for the reliability layer.

Tests the full stack including retry, circuit breakers, and error handling.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncGenerator

from steer_llm_sdk.core.routing.router import LLMRouter
from steer_llm_sdk.models.generation import GenerationParams, ProviderType
from steer_llm_sdk.models.conversation_types import ConversationMessage
from steer_llm_sdk.providers.base import ProviderError
from steer_llm_sdk.reliability import CircuitState


class TestReliabilityIntegration:
    """Test reliability features integrated with the router."""
    
    @pytest.fixture
    def router(self):
        """Create a router instance."""
        return LLMRouter()
    
    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider."""
        provider = MagicMock()
        provider.is_available = MagicMock(return_value=True)
        return provider
    
    @pytest.mark.asyncio
    async def test_generate_with_retry(self, router, mock_provider):
        """Test generate with retry on transient errors."""
        # Mock provider that fails once then succeeds
        call_count = 0
        
        async def mock_generate(messages, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                error = ProviderError(
                    "Rate limit exceeded",
                    provider="openai",
                    status_code=429
                )
                error.is_retryable = True
                error.original_error = Exception("Rate limit")
                from steer_llm_sdk.reliability import ErrorCategory
                error.error_category = ErrorCategory.RATE_LIMIT
                raise error
            return MagicMock(
                choices=[MagicMock(message=MagicMock(content="Success"))],
                usage=MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30),
                model="gpt-4o-mini"
            )
        
        mock_provider.generate = mock_generate
        
        # Patch the provider
        with patch.object(router, 'providers', {ProviderType.OPENAI: mock_provider}):
            with patch('steer_llm_sdk.core.routing.selector.get_config') as mock_config:
                mock_config.return_value = MagicMock(
                    provider=ProviderType.OPENAI,
                    model_id="gpt-4o-mini"
                )
                
                # Call generate
                response = await router.generate(
                    messages=[ConversationMessage(role="user", content="Hello")],
                    llm_model_id="gpt-4o-mini",
                    raw_params={}
                )
                
                # Should succeed after retry
                assert response.choices[0].message.content == "Success"
                assert call_count == 2  # Failed once, succeeded on retry
    
    @pytest.mark.asyncio
    async def test_streaming_with_retry(self, router, mock_provider):
        """Test streaming with retry on connection errors."""
        attempt_count = 0
        
        async def mock_stream_generator():
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count == 1:
                # First attempt fails after some chunks
                yield "Hello"
                yield " "
                raise Exception("Connection error")
            else:
                # Second attempt succeeds
                yield "World"
                yield "!"
        
        mock_provider.generate_stream = lambda messages, params: mock_stream_generator()
        
        # Patch the provider
        with patch.object(router, 'providers', {ProviderType.OPENAI: mock_provider}):
            with patch('steer_llm_sdk.core.routing.selector.get_config') as mock_config:
                mock_config.return_value = MagicMock(
                    provider=ProviderType.OPENAI,
                    model_id="gpt-4o-mini"
                )
                
                # Collect streamed chunks
                chunks = []
                async for chunk in router.generate_stream(
                    messages=[ConversationMessage(role="user", content="Hello")],
                    llm_model_id="gpt-4o-mini",
                    raw_params={}
                ):
                    chunks.append(chunk)
                
                # Should get all chunks after retry
                assert chunks == ["Hello", " ", "World", "!"]
                assert attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self, router, mock_provider):
        """Test circuit breaker opens after consecutive failures."""
        # Mock provider that always fails
        async def mock_generate(messages, params):
            error = ProviderError(
                "Server error",
                provider="openai",
                status_code=500
            )
            error.is_retryable = True
            raise error
        
        mock_provider.generate = mock_generate
        
        # Get circuit breaker
        circuit_breaker = router.circuit_manager.get_or_create("openai")
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        
        # Patch the provider
        with patch.object(router, 'providers', {ProviderType.OPENAI: mock_provider}):
            with patch('steer_llm_sdk.core.routing.selector.get_config') as mock_config:
                mock_config.return_value = MagicMock(
                    provider=ProviderType.OPENAI,
                    model_id="gpt-4o-mini"
                )
                
                # Make multiple requests that will fail
                for i in range(5):
                    with pytest.raises(Exception):
                        await router.generate(
                            messages=[ConversationMessage(role="user", content="Hello")],
                            llm_model_id="gpt-4o-mini",
                            raw_params={}
                        )
                
                # Circuit should be open after failures
                assert circuit_breaker.get_state() == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_streaming_preserves_partial_response(self, router):
        """Test streaming preserves partial response on failure."""
        async def mock_stream_generator():
            yield "Partial"
            yield " response"
            raise Exception("Stream interrupted")
        
        mock_provider = MagicMock()
        mock_provider.is_available = MagicMock(return_value=True)
        mock_provider.generate_stream = lambda messages, params: mock_stream_generator()
        
        # Patch the provider
        with patch.object(router, 'providers', {ProviderType.OPENAI: mock_provider}):
            with patch('steer_llm_sdk.core.routing.selector.get_config') as mock_config:
                mock_config.return_value = MagicMock(
                    provider=ProviderType.OPENAI,
                    model_id="gpt-4o-mini"
                )
                
                chunks = []
                try:
                    async for chunk in router.generate_stream(
                        messages=[ConversationMessage(role="user", content="Hello")],
                        llm_model_id="gpt-4o-mini",
                        raw_params={"request_id": "test-partial"}
                    ):
                        chunks.append(chunk)
                except Exception:
                    pass
                
                # Should have received partial response
                assert chunks == ["Partial", " response"]
                
                # Check if partial response is available
                partial = router.streaming_retry_manager.get_partial_response("test-partial")
                assert partial == "Partial response"
    
    @pytest.mark.asyncio 
    async def test_retry_metrics_tracking(self, router, mock_provider):
        """Test retry metrics are tracked correctly."""
        # Reset metrics
        router.retry_manager.reset_metrics()
        
        # Mock provider that fails twice then succeeds
        call_count = 0
        
        async def mock_generate(messages, params):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                error = ProviderError(
                    "Rate limit exceeded",
                    provider="openai", 
                    status_code=429
                )
                error.is_retryable = True
                raise error
            return MagicMock(
                choices=[MagicMock(message=MagicMock(content="Success"))],
                usage=MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30),
                model="gpt-4o-mini"
            )
        
        mock_provider.generate = mock_generate
        
        # Patch the provider
        with patch.object(router, 'providers', {ProviderType.OPENAI: mock_provider}):
            with patch('steer_llm_sdk.core.routing.selector.get_config') as mock_config:
                mock_config.return_value = MagicMock(
                    provider=ProviderType.OPENAI,
                    model_id="gpt-4o-mini"
                )
                
                # Make request
                await router.generate(
                    messages=[ConversationMessage(role="user", content="Hello")],
                    llm_model_id="gpt-4o-mini",
                    raw_params={}
                )
                
                # Check metrics
                metrics = router.get_retry_metrics()
                assert metrics['retry_successes']['openai'] == 1
                assert len(metrics['retry_attempts']) > 0