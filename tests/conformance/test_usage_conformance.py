"""Conformance tests for usage data normalization.

These tests ensure that all providers normalize usage data to a consistent format
regardless of their native API response structure.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from steer_llm_sdk.providers.openai import OpenAIProvider
from steer_llm_sdk.providers.anthropic import AnthropicProvider
from steer_llm_sdk.providers.xai import XAIProvider
from steer_llm_sdk.models.generation import GenerationParams
from tests.helpers.streaming_mocks import (
    create_openai_stream, create_anthropic_stream, create_xai_stream
)


class TestUsageConformance:
    """Test that all providers normalize usage data consistently."""
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_usage_structure(self, provider_class, model):
        """Test that usage data has the required structure."""
        provider = provider_class()
        
        # Mock responses with usage data
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test"
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )
            # Mock the model_dump method to return proper dict
            mock_response.usage.model_dump.return_value = {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Test"
            mock_response.stop_reason = "end_turn"
            # Anthropic uses different field names
            mock_response.usage = MagicMock(
                input_tokens=10,
                output_tokens=5
            )
            # Mock the model_dump method to return proper dict
            mock_response.usage.model_dump.return_value = {
                "input_tokens": 10,
                "output_tokens": 5
            }
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == XAIProvider:
            # xAI uses a different response structure
            mock_response = MagicMock()
            mock_response.content = "Test"
            mock_response.finish_reason = "stop"
            # xAI has a two-step process: create chat, then sample
            mock_chat = MagicMock()
            mock_chat.sample = AsyncMock(return_value=mock_response)
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
        
        params = GenerationParams(model=model)
        response = await provider.generate("Test prompt", params)
        
        # Check required fields
        assert isinstance(response.usage, dict)
        assert "prompt_tokens" in response.usage
        assert "completion_tokens" in response.usage
        assert "total_tokens" in response.usage
        
        # Check types
        assert isinstance(response.usage["prompt_tokens"], int)
        assert isinstance(response.usage["completion_tokens"], int)
        assert isinstance(response.usage["total_tokens"], int)
        
        # Check consistency
        if provider_class != XAIProvider:  # xAI might not provide real usage
            assert response.usage["total_tokens"] == (
                response.usage["prompt_tokens"] + response.usage["completion_tokens"]
            )
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
    ])
    async def test_usage_with_cache_info(self, provider_class, model):
        """Test that cache info is included when available."""
        provider = provider_class()
        
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Cached response"
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock(
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120,
                # OpenAI might add cache info in the future
                prompt_tokens_details=MagicMock(cached_tokens=50)
            )
            # Mock the model_dump method to return proper dict
            mock_response.usage.model_dump.return_value = {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {"cached_tokens": 50}
            }
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Cached response"
            mock_response.stop_reason = "end_turn"
            mock_response.usage = MagicMock(
                input_tokens=100,
                output_tokens=20,
                # Anthropic provides cache info
                cache_creation_input_tokens=0,
                cache_read_input_tokens=50
            )
            # Mock the model_dump method to return proper dict
            mock_response.usage.model_dump.return_value = {
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 50
            }
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
        
        params = GenerationParams(model=model)
        response = await provider.generate("Test with cache", params)
        
        assert "cache_info" in response.usage
        assert isinstance(response.usage["cache_info"], dict)
        
        if provider_class == AnthropicProvider:
            # Anthropic should include cache read tokens
            assert "cache_read_input_tokens" in response.usage["cache_info"]
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_streaming_usage_normalization(self, provider_class, model):
        """Test that usage is normalized correctly in streaming mode."""
        provider = provider_class()
        
        if provider_class == OpenAIProvider:
            # Use the streaming mock helper
            async def create_stream(**kwargs):
                if kwargs.get("stream"):
                    return create_openai_stream(["Hello", " world"])
                # Non-streaming response
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Hello world"
                return mock_response
            
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(side_effect=create_stream)
            # Also mock Responses API in case it's used
            provider._client.responses.create = AsyncMock(side_effect=create_stream)
            
        elif provider_class == AnthropicProvider:
            # Use the streaming mock helper
            async def create_stream(**kwargs):
                if kwargs.get("stream"):
                    return create_anthropic_stream(["Hello", " world"])
                # Non-streaming response
                mock_response = MagicMock()
                mock_response.content = [MagicMock()]
                mock_response.content[0].text = "Hello world"
                return mock_response
            
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(side_effect=create_stream)
            
        elif provider_class == XAIProvider:
            # xAI has a two-step process
            mock_chat = MagicMock()
            mock_chat.stream = lambda: create_xai_stream(["Hello", " world"])
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
        
        params = GenerationParams(model=model)
        
        # Collect streaming results
        text_chunks = []
        final_usage = None
        
        async for chunk, usage in provider.generate_stream_with_usage("Test", params):
            if chunk:
                text_chunks.append(chunk)
            if usage:
                final_usage = usage
        
        # Verify we got text
        assert len(text_chunks) > 0
        full_text = "".join(text_chunks)
        assert len(full_text) > 0
        
        # Verify final usage
        assert final_usage is not None
        assert "usage" in final_usage
        usage_data = final_usage["usage"]
        
        # Check normalized structure
        assert "prompt_tokens" in usage_data
        assert "completion_tokens" in usage_data
        assert "total_tokens" in usage_data
        
        # For providers that provide real usage, verify values
        if provider_class in (OpenAIProvider, AnthropicProvider):
            assert usage_data["prompt_tokens"] > 0
            assert usage_data["completion_tokens"] > 0
            assert usage_data["total_tokens"] == (
                usage_data["prompt_tokens"] + usage_data["completion_tokens"]
            )
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_missing_usage_handling(self, provider_class, model):
        """Test that missing usage data is handled gracefully."""
        provider = provider_class()
        
        # Mock responses without usage data
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "No usage"
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = None  # No usage data
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "No usage"
            mock_response.stop_reason = "end_turn"
            mock_response.usage = None  # No usage data
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == XAIProvider:
            # xAI uses a different response structure
            mock_response = MagicMock()
            mock_response.content = "No usage"
            mock_response.finish_reason = "stop"
            # xAI has a two-step process: create chat, then sample
            mock_chat = MagicMock()
            mock_chat.sample = AsyncMock(return_value=mock_response)
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
        
        params = GenerationParams(model=model)
        response = await provider.generate("Test", params)
        
        # Should still have usage dict with default values
        assert isinstance(response.usage, dict)
        assert "prompt_tokens" in response.usage
        assert "completion_tokens" in response.usage
        assert "total_tokens" in response.usage
        
        # Values should be integers (even if 0)
        assert isinstance(response.usage["prompt_tokens"], int)
        assert isinstance(response.usage["completion_tokens"], int)
        assert isinstance(response.usage["total_tokens"], int)
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_usage_field_types(self, provider_class, model):
        """Test that usage fields are always the correct type."""
        provider = provider_class()
        
        # Mock responses with various usage data types
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test"
            mock_response.choices[0].finish_reason = "stop"
            # Test with string values that should be converted
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = "10"  # String instead of int
            mock_response.usage.completion_tokens = 5.5  # Float instead of int
            mock_response.usage.total_tokens = 15
            # Mock the model_dump method to return the raw values
            mock_response.usage.model_dump.return_value = {
                "prompt_tokens": "10",  # String
                "completion_tokens": 5.5,  # Float
                "total_tokens": 15
            }
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Test"
            mock_response.stop_reason = "end_turn"
            mock_response.usage = MagicMock()
            mock_response.usage.input_tokens = "10"  # String
            mock_response.usage.output_tokens = 5.5  # Float
            # Mock the model_dump method to return the raw values
            mock_response.usage.model_dump.return_value = {
                "input_tokens": "10",  # String
                "output_tokens": 5.5  # Float
            }
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == XAIProvider:
            # xAI uses a different response structure
            mock_response = MagicMock()
            mock_response.content = "Test"
            mock_response.finish_reason = "stop"
            # xAI has a two-step process: create chat, then sample
            mock_chat = MagicMock()
            mock_chat.sample = AsyncMock(return_value=mock_response)
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
        
        params = GenerationParams(model=model)
        response = await provider.generate("Test", params)
        
        # All token counts should be integers
        assert isinstance(response.usage["prompt_tokens"], int)
        assert isinstance(response.usage["completion_tokens"], int)
        assert isinstance(response.usage["total_tokens"], int)
        
        # Values should be non-negative
        assert response.usage["prompt_tokens"] >= 0
        assert response.usage["completion_tokens"] >= 0
        assert response.usage["total_tokens"] >= 0