"""End-to-end integration tests for Steer LLM SDK."""

import pytest
from unittest.mock import patch
import os

from steer_llm_sdk import (
    LLMRouter,
    SteerLLMClient,
    ConversationMessage,
    TurnRole as ConversationRole,
    get_available_models,
    generate
)


@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_client_simple_generation(self, mock_providers):
        """Test simple generation through client."""
        client = SteerLLMClient()
        
        result = await client.generate(
            "What is 2+2?",
            model="GPT-4o Mini",
            temperature=0.5,
            max_tokens=50
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_client_conversation_generation(self, mock_providers):
        """Test conversation generation through client."""
        client = SteerLLMClient()
        
        messages = [
            ConversationMessage(
                role=ConversationRole.SYSTEM,
                content="You are a math tutor"
            ),
            ConversationMessage(
                role=ConversationRole.USER,
                content="Explain addition"
            )
        ]
        
        result = await client.generate(
            messages,
            model="Claude 3.5 Sonnet",
            temperature=0.7
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_client_streaming(self, mock_providers):
        """Test streaming through client."""
        client = SteerLLMClient()
        
        chunks = []
        async for chunk in client.stream(
            "Write a haiku",
            model="GPT-4o Mini",
            temperature=0.8
        ):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert len(full_response) > 0
    
    def test_get_available_models(self, raw_model_configs):
        """Test getting available models."""
        with patch('steer_llm_sdk.llm.registry.MODEL_CONFIGS', raw_model_configs):
            models = get_available_models()
            
            assert isinstance(models, dict)
            assert len(models) > 0
            # All models should be enabled
            for model_id, config in models.items():
                assert config["enabled"] is True
    
    def test_client_model_availability_check(self, mock_env_vars):
        """Test checking model availability."""
        client = SteerLLMClient()
        
        # Should be available with mocked env vars
        assert client.check_model_availability("GPT-4o Mini") is True
    
    @pytest.mark.asyncio
    async def test_quick_generate_function(self, mock_providers):
        """Test the convenience generate function."""
        result = await generate(
            "Hello world",
            model="GPT-4o Mini",
            temperature=0.5
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_router_with_multiple_providers(self, mock_providers):
        """Test router switching between providers."""
        router = LLMRouter()
        
        # Test OpenAI provider
        with patch('steer_llm_sdk.llm.registry.get_config') as mock_config:
            mock_config.return_value.provider = "openai"
            
            response = await router.generate(
                "Test OpenAI",
                "GPT-4o Mini",
                {"temperature": 0.7}
            )
            
            assert response.provider == "openai"
        
        # Test Anthropic provider
        with patch('steer_llm_sdk.llm.registry.get_config') as mock_config:
            mock_config.return_value.provider = "anthropic"
            
            response = await router.generate(
                "Test Anthropic",
                "Claude 3.5 Sonnet",
                {"temperature": 0.7}
            )
            
            assert response.provider == "anthropic"
    
    @pytest.mark.asyncio
    async def test_error_handling_no_api_key(self):
        """Test error handling when API key is missing."""
        with patch.dict('os.environ', {}, clear=True):
            router = LLMRouter()
            
            with pytest.raises(Exception) as exc_info:
                await router.generate(
                    "Test",
                    "GPT-4o Mini",
                    {}
                )
            
            assert "not available" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_conversation_flow(self, mock_providers):
        """Test a complete conversation flow."""
        client = SteerLLMClient()
        
        conversation = []
        
        # System message
        conversation.append(ConversationMessage(
            role=ConversationRole.SYSTEM,
            content="You are a helpful assistant"
        ))
        
        # First user message
        conversation.append(ConversationMessage(
            role=ConversationRole.USER,
            content="What's the capital of France?"
        ))
        
        # Get first response
        response1 = await client.generate(conversation, model="GPT-4o Mini")
        
        # Add assistant response to conversation
        conversation.append(ConversationMessage(
            role=ConversationRole.ASSISTANT,
            content=response1
        ))
        
        # Second user message
        conversation.append(ConversationMessage(
            role=ConversationRole.USER,
            content="What about Germany?"
        ))
        
        # Get second response
        response2 = await client.generate(conversation, model="GPT-4o Mini")
        
        assert isinstance(response1, str)
        assert isinstance(response2, str)
        assert len(conversation) == 4  # System + 2 user + 1 assistant
    
    @pytest.mark.asyncio
    async def test_parameter_validation(self, mock_providers):
        """Test parameter validation."""
        client = SteerLLMClient()
        
        # Test with invalid temperature (should be clamped)
        result = await client.generate(
            "Test",
            temperature=5.0,  # Too high, should be clamped to 2.0
            max_tokens=10
        )
        
        assert isinstance(result, str)
        
        # Test with invalid max_tokens (should be clamped)
        result = await client.generate(
            "Test",
            max_tokens=10000  # Too high, should be clamped to model limit
        )
        
        assert isinstance(result, str)