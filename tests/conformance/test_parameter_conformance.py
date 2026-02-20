"""Conformance tests for parameter handling.

These tests ensure that all providers correctly handle GenerationParams
and map them to provider-specific parameters using capability-driven logic.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from steer_llm_sdk.providers.openai import OpenAIProvider
from steer_llm_sdk.providers.anthropic import AnthropicProvider
from steer_llm_sdk.providers.xai import XAIProvider
from steer_llm_sdk.models.generation import GenerationParams
from steer_llm_sdk.core.capabilities import get_capabilities_for_model


class TestParameterConformance:
    """Test that all providers handle parameters consistently."""
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_basic_parameter_mapping(self, provider_class, model):
        """Test that basic parameters are mapped correctly."""
        provider = provider_class()
        
        # Mock successful response
        mock_response = self._create_mock_response(provider_class)
        self._mock_provider_client(provider, provider_class, mock_response)
        
        # Test with common parameters
        params = GenerationParams(
            model=model,
            temperature=0.7,
            max_tokens=100,
            top_p=0.9,
            presence_penalty=0.1,
            frequency_penalty=0.2
        )
        
        await provider.generate("Test", params)
        
        # Verify API was called with correct parameters
        call_args = self._get_api_call_args(provider, provider_class)
        caps = get_capabilities_for_model(model)
        
        assert call_args["model"] == model
        
        # Temperature may be clamped based on capabilities
        expected_temp = 0.7
        if caps.deterministic_temperature_max is not None and expected_temp > caps.deterministic_temperature_max:
            expected_temp = caps.deterministic_temperature_max
        assert call_args["temperature"] == expected_temp
        
        assert "max_tokens" in call_args or "max_completion_tokens" in call_args
        assert call_args["top_p"] == 0.9
        
        # Check provider-specific parameter names
        if provider_class == OpenAIProvider:
            assert call_args["presence_penalty"] == 0.1
            assert call_args["frequency_penalty"] == 0.2
        elif provider_class == AnthropicProvider:
            # Anthropic might use different parameter names
            assert "temperature" in call_args
    
    @pytest.mark.parametrize("provider_class,model,deterministic", [
        (OpenAIProvider, "gpt-4o-mini", True),
        (OpenAIProvider, "gpt-4o-mini", False),
        (AnthropicProvider, "claude-3-haiku-20240307", True),
        (AnthropicProvider, "claude-3-haiku-20240307", False),
        (XAIProvider, "grok-beta", True),
        (XAIProvider, "grok-beta", False)
    ])
    async def test_deterministic_mode(self, provider_class, model, deterministic):
        """Test that deterministic mode is handled correctly."""
        provider = provider_class()
        
        mock_response = self._create_mock_response(provider_class)
        self._mock_provider_client(provider, provider_class, mock_response)
        
        params = GenerationParams(
            model=model,
            temperature=0.7,  # Should be overridden in deterministic mode
            deterministic=deterministic
        )
        
        await provider.generate("Test", params)
        
        call_args = self._get_api_call_args(provider, provider_class)
        caps = get_capabilities_for_model(model)
        
        if deterministic:
            # In deterministic mode, temperature should be 0.0 or clamped to deterministic_temperature_max
            expected_temp = 0.0
            if caps.deterministic_temperature_max is not None and expected_temp > caps.deterministic_temperature_max:
                expected_temp = caps.deterministic_temperature_max
            assert call_args["temperature"] == expected_temp
            
            # Seed should be set if supported
            if caps.supports_seed:
                assert "seed" in call_args
                assert isinstance(call_args["seed"], int)
        else:
            # Non-deterministic mode should use provided temperature (may be clamped)
            expected_temp = 0.7
            if caps.deterministic_temperature_max is not None and expected_temp > caps.deterministic_temperature_max:
                expected_temp = caps.deterministic_temperature_max
            assert call_args["temperature"] == expected_temp
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o"),
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-5-sonnet-20241022"),
        (AnthropicProvider, "claude-3-haiku-20240307")
    ])
    async def test_max_tokens_field_mapping(self, provider_class, model):
        """Test that max_tokens is mapped to correct field based on capabilities."""
        provider = provider_class()
        
        mock_response = self._create_mock_response(provider_class)
        self._mock_provider_client(provider, provider_class, mock_response)
        
        params = GenerationParams(
            model=model,
            max_tokens=100
        )
        
        await provider.generate("Test", params)
        
        call_args = self._get_api_call_args(provider, provider_class)
        caps = get_capabilities_for_model(model)
        
        # Check if max_tokens is mapped correctly based on capabilities
        if caps.uses_max_completion_tokens:
            assert "max_completion_tokens" in call_args
            assert call_args["max_completion_tokens"] == 100
            assert "max_tokens" not in call_args
        else:
            assert "max_tokens" in call_args
            assert call_args["max_tokens"] == 100
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_stop_sequences_handling(self, provider_class, model):
        """Test that stop sequences are handled correctly."""
        provider = provider_class()
        
        mock_response = self._create_mock_response(provider_class)
        self._mock_provider_client(provider, provider_class, mock_response)
        
        params = GenerationParams(
            model=model,
            stop=["END", "STOP", "\n\n"]
        )
        
        await provider.generate("Test", params)
        
        call_args = self._get_api_call_args(provider, provider_class)
        
        # All providers should support stop sequences
        if provider_class == OpenAIProvider:
            assert "stop" in call_args
            assert call_args["stop"] == ["END", "STOP", "\n\n"]
        elif provider_class == AnthropicProvider:
            assert "stop_sequences" in call_args
            assert call_args["stop_sequences"] == ["END", "STOP", "\n\n"]
        elif provider_class == XAIProvider:
            assert "stop" in call_args
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o"),
        (AnthropicProvider, "claude-3-5-sonnet-20241022"),
    ])
    async def test_json_schema_handling(self, provider_class, model):
        """Test that JSON schema response format is handled correctly."""
        provider = provider_class()
        
        mock_response = self._create_mock_response(provider_class)
        self._mock_provider_client(provider, provider_class, mock_response)
        
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name", "age"]
        }
        
        params = GenerationParams(
            model=model,
            response_format={
                "type": "json_schema",
                "json_schema": schema
            }
        )
        
        await provider.generate("Test", params)
        
        call_args = self._get_api_call_args(provider, provider_class)
        caps = get_capabilities_for_model(model)
        
        if caps.supports_json_schema:
            if provider_class == OpenAIProvider:
                # OpenAI uses Responses API for JSON schema
                assert "text" in call_args
                assert call_args["text"]["format"]["type"] == "json_schema"
                assert "schema" in call_args["text"]["format"]
            else:
                # Other providers use response_format
                assert "response_format" in call_args
    
    @pytest.mark.parametrize("provider_class,model", [
        (OpenAIProvider, "gpt-4o-mini"),
        (AnthropicProvider, "claude-3-haiku-20240307"),
        (XAIProvider, "grok-beta")
    ])
    async def test_unsupported_parameter_handling(self, provider_class, model):
        """Test that unsupported parameters are handled gracefully."""
        provider = provider_class()
        
        mock_response = self._create_mock_response(provider_class)
        self._mock_provider_client(provider, provider_class, mock_response)
        
        # Add some parameters that might not be supported by all providers
        params = GenerationParams(
            model=model,
            temperature=0.7,
            max_tokens=100,
            logit_bias={50256: -100},  # Not all providers support this
            user="test-user",  # Not all providers support this
            n=1  # Not all providers support multiple completions
        )
        
        # Should not raise an error
        response = await provider.generate("Test", params)
        assert response is not None
        
        call_args = self._get_api_call_args(provider, provider_class)
        
        # Basic parameters should always be present
        assert "temperature" in call_args
        assert "max_tokens" in call_args or "max_completion_tokens" in call_args
    
    # Helper methods
    def _create_mock_response(self, provider_class):
        """Create a mock response for the provider."""
        if provider_class == OpenAIProvider:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )
            return mock_response
            
        elif provider_class == AnthropicProvider:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Test response"
            mock_response.stop_reason = "end_turn"
            mock_response.usage = MagicMock(
                input_tokens=10,
                output_tokens=5
            )
            return mock_response
            
        elif provider_class == XAIProvider:
            # xAI uses a different response structure
            mock_response = MagicMock()
            mock_response.content = "Test response"
            mock_response.finish_reason = "stop"
            return mock_response
    
    def _mock_provider_client(self, provider, provider_class, mock_response):
        """Mock the provider's API client."""
        if provider_class == OpenAIProvider:
            provider._client = MagicMock()
            provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
            # Also mock Responses API for JSON schema tests
            responses_mock = MagicMock()
            responses_mock.output_text = "Test response"
            responses_mock.usage = MagicMock(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )
            provider._client.responses.create = AsyncMock(return_value=responses_mock)
            
        elif provider_class == AnthropicProvider:
            provider._client = MagicMock()
            provider._client.messages.create = AsyncMock(return_value=mock_response)
            
        elif provider_class == XAIProvider:
            # xAI has a two-step process: create chat, then sample
            mock_chat = MagicMock()
            mock_chat.sample = AsyncMock(return_value=mock_response)
            provider._client = MagicMock()
            provider._client.chat.create = AsyncMock(return_value=mock_chat)
    
    def _get_api_call_args(self, provider, provider_class):
        """Get the arguments passed to the API call."""
        if provider_class == OpenAIProvider:
            # Check if Responses API was used (for JSON schema)
            if provider._client.responses.create.called:
                return provider._client.responses.create.call_args[1]
            else:
                return provider._client.chat.completions.create.call_args[1]
        elif provider_class == AnthropicProvider:
            return provider._client.messages.create.call_args[1]
        elif provider_class == XAIProvider:
            return provider._client.chat.create.call_args[1]