"""Conformance tests for provider generation methods.

These tests ensure that all providers correctly implement the generate() method
and return responses in the expected format.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from steer_llm_sdk.providers.openai import OpenAIProvider
from steer_llm_sdk.providers.anthropic import AnthropicProvider
from steer_llm_sdk.providers.xai import XAIProvider
from steer_llm_sdk.models.generation import GenerationParams, GenerationResponse
from steer_llm_sdk.models.conversation_types import ConversationMessage, TurnRole


class TestGenerationConformance:
    """Test that all providers conform to generation interface."""
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_generate_returns_correct_type(self, provider_class, model):
        """Test that generate() returns GenerationResponse."""
        provider = provider_class()
        
        # Mock the API client
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].finish_reason = "stop"
            usage_mock = MagicMock(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )
            usage_mock.model_dump.return_value = {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
            mock_response.usage = usage_mock
            
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            content_block = MagicMock()
            content_block.type = "text"
            content_block.text = "Test response"
            mock_response.content = [content_block]
            mock_response.stop_reason = "end_turn"
            usage_mock = MagicMock(
                input_tokens=10,
                output_tokens=5
            )
            usage_mock.model_dump.return_value = {
                "input_tokens": 10,
                "output_tokens": 5
            }
            mock_response.usage = usage_mock
            
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == XAIProvider:
            # xAI has a two-step process: create chat, then sample
            mock_response = MagicMock()
            mock_response.content = "Test response"
            mock_response.finish_reason = "stop"
            
            mock_chat = MagicMock()
            mock_chat.sample = AsyncMock(return_value=mock_response)
            
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
        
        # Test generation
        params = GenerationParams(model=model)
        response = await provider.generate("Test prompt", params)
        
        # Verify response type and required fields
        assert isinstance(response, GenerationResponse)
        assert isinstance(response.text, str)
        assert response.model == model
        assert response.provider == provider_class.__name__.replace("Provider", "").lower()
        assert isinstance(response.usage, dict)
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_generate_with_conversation(self, provider_class, model):
        """Test that all providers handle conversation messages correctly."""
        provider = provider_class()
        
        # Mock responses (same as above)
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "I can help with math"
            mock_response.choices[0].finish_reason = "stop"
            usage_mock = MagicMock(
                prompt_tokens=15,
                completion_tokens=8,
                total_tokens=23
            )
            usage_mock.model_dump.return_value = {
                "prompt_tokens": 15,
                "completion_tokens": 8,
                "total_tokens": 23
            }
            mock_response.usage = usage_mock
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            content_block = MagicMock()
            content_block.type = "text"
            content_block.text = "I can help with math"
            mock_response.content = [content_block]
            mock_response.stop_reason = "end_turn"
            usage_mock = MagicMock(
                input_tokens=15,
                output_tokens=8
            )
            usage_mock.model_dump.return_value = {
                "input_tokens": 15,
                "output_tokens": 8
            }
            mock_response.usage = usage_mock
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == XAIProvider:
            # xAI has a two-step process: create chat, then sample
            mock_response = MagicMock()
            mock_response.content = "I can help with math"
            mock_response.finish_reason = "stop"
            
            mock_chat = MagicMock()
            mock_chat.sample = AsyncMock(return_value=mock_response)
            
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
        
        # Test with conversation messages
        messages = [
            ConversationMessage(role=TurnRole.SYSTEM, content="You are a math tutor"),
            ConversationMessage(role=TurnRole.USER, content="Can you help me?")
        ]
        
        params = GenerationParams(model=model)
        response = await provider.generate(messages, params)
        
        assert isinstance(response, GenerationResponse)
        assert len(response.text) > 0
        assert response.model == model
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_usage_normalization(self, provider_class, model):
        """Test that usage data is normalized across all providers."""
        provider = provider_class()
        
        # Mock responses with different usage formats
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test"
            mock_response.choices[0].finish_reason = "stop"
            usage_mock = MagicMock(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )
            usage_mock.model_dump.return_value = {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
            mock_response.usage = usage_mock
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            content_block = MagicMock()
            content_block.type = "text"
            content_block.text = "Test"
            mock_response.content = [content_block]
            mock_response.stop_reason = "end_turn"
            # Anthropic uses different field names
            usage_mock = MagicMock(
                input_tokens=10,  # Different from OpenAI's prompt_tokens
                output_tokens=5   # Different from OpenAI's completion_tokens
            )
            usage_mock.model_dump.return_value = {
                "input_tokens": 10,
                "output_tokens": 5
            }
            mock_response.usage = usage_mock
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == XAIProvider:
            # xAI has a two-step process: create chat, then sample
            mock_response = MagicMock()
            mock_response.content = "Test"
            mock_response.finish_reason = "stop"
            # xAI might not provide usage
            
            mock_chat = MagicMock()
            mock_chat.sample = AsyncMock(return_value=mock_response)
            
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
        
        params = GenerationParams(model=model)
        response = await provider.generate("Test", params)
        
        # All providers should normalize to this structure
        assert "prompt_tokens" in response.usage
        assert "completion_tokens" in response.usage
        assert "total_tokens" in response.usage
        assert isinstance(response.usage["prompt_tokens"], int)
        assert isinstance(response.usage["completion_tokens"], int)
        assert isinstance(response.usage["total_tokens"], int)
        
        # For providers that provide usage, verify consistency
        if provider_class != XAIProvider:
            assert response.usage["prompt_tokens"] >= 0
            assert response.usage["completion_tokens"] >= 0
            assert response.usage["total_tokens"] == (
                response.usage["prompt_tokens"] + response.usage["completion_tokens"]
            )
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_parameter_handling(self, provider_class, model):
        """Test that all providers handle GenerationParams correctly."""
        provider = provider_class()
        
        # Mock successful responses
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Generated with params"
            mock_response.choices[0].finish_reason = "length"
            usage_mock = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            usage_mock.model_dump.return_value = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
            mock_response.usage = usage_mock
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            content_block = MagicMock()
            content_block.type = "text"
            content_block.text = "Generated with params"
            mock_response.content = [content_block]
            mock_response.stop_reason = "max_tokens"
            usage_mock = MagicMock(input_tokens=10, output_tokens=5)
            usage_mock.model_dump.return_value = {"input_tokens": 10, "output_tokens": 5}
            mock_response.usage = usage_mock
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == XAIProvider:
            # xAI has a two-step process: create chat, then sample
            mock_response = MagicMock()
            mock_response.content = "Generated with params"
            mock_response.finish_reason = "length"
            
            mock_chat = MagicMock()
            mock_chat.sample = AsyncMock(return_value=mock_response)
            
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
        
        # Test with various parameters
        params = GenerationParams(
            model=model,
            temperature=0.7,
            max_tokens=100,
            top_p=0.9,
            stop=["END"],
            seed=42
        )
        
        response = await provider.generate("Generate something", params)
        
        assert isinstance(response, GenerationResponse)
        assert response.model == model
        
        # Verify the provider called the API with transformed parameters
        if provider_class == OpenAIProvider:
            call_args = provider.client.chat.completions.create.call_args[1]
            assert "temperature" in call_args
            assert "max_tokens" in call_args
            
        elif provider_class == AnthropicProvider:
            call_args = provider.client.messages.create.call_args[1]
            assert "temperature" in call_args
            assert "max_tokens" in call_args
            
        elif provider_class == XAIProvider:
            call_args = provider._client.chat.create.call_args[1]
            # xAI should also receive normalized params
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_empty_response_handling(self, provider_class, model):
        """Test that providers handle empty responses gracefully."""
        provider = provider_class()
        
        # Mock empty responses
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = ""
            mock_response.choices[0].finish_reason = "stop"
            usage_mock = MagicMock(prompt_tokens=10, completion_tokens=0, total_tokens=10)
            usage_mock.model_dump.return_value = {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10}
            mock_response.usage = usage_mock
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            content_block = MagicMock()
            content_block.type = "text"
            content_block.text = ""
            mock_response.content = [content_block]
            mock_response.stop_reason = "end_turn"
            usage_mock = MagicMock(input_tokens=10, output_tokens=0)
            usage_mock.model_dump.return_value = {"input_tokens": 10, "output_tokens": 0}
            mock_response.usage = usage_mock
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == XAIProvider:
            # xAI has a two-step process: create chat, then sample
            mock_response = MagicMock()
            mock_response.content = ""
            mock_response.finish_reason = "stop"
            
            mock_chat = MagicMock()
            mock_chat.sample = AsyncMock(return_value=mock_response)
            
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
        
        params = GenerationParams(model=model)
        response = await provider.generate("Test", params)
        
        assert isinstance(response, GenerationResponse)
        assert response.text == ""
        assert response.model == model
        assert isinstance(response.usage, dict)