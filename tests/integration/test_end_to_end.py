"""End-to-end integration tests for Steer LLM SDK."""

import pytest
from unittest.mock import patch
import os

from steer_llm_sdk import (
    LLMRouter,
    SteerLLMClient,
    ConversationMessage,
    ConversationRole,
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
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=50
        )
        
        from steer_llm_sdk.models.generation import GenerationResponse
        assert isinstance(result, GenerationResponse)
        assert isinstance(result.text, str)
        assert len(result.text) > 0
    
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
            model="claude-3-haiku",
            temperature=0.7
        )
        
        from steer_llm_sdk.models.generation import GenerationResponse
        assert isinstance(result, GenerationResponse)
        assert isinstance(result.text, str)
        assert len(result.text) > 0
    
    @pytest.mark.asyncio
    async def test_client_streaming(self, mock_providers):
        """Test streaming through client."""
        client = SteerLLMClient()
        
        chunks = []
        async for chunk in client.stream(
            "Write a haiku",
            model="gpt-4o-mini",
            temperature=0.8
        ):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert len(full_response) > 0
    
    def test_get_available_models(self):
        """Test getting available models."""
        models = get_available_models()
        
        assert isinstance(models, dict)
        assert len(models) > 0
        # All models should be ModelConfig objects with enabled=True
        for model_id, config in models.items():
            assert hasattr(config, 'enabled')
            assert config.enabled is True
    
    def test_client_model_availability_check(self, mock_env_vars):
        """Test checking model availability."""
        client = SteerLLMClient()
        
        # Should be available with mocked env vars
        assert client.check_model_availability("gpt-4o-mini") is True
    
    @pytest.mark.asyncio
    async def test_quick_generate_function(self, mock_providers):
        """Test the convenience generate function."""
        result = await generate(
            "Hello world",
            model="gpt-4o-mini",
            temperature=0.5
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_router_with_multiple_providers(self, mock_providers):
        """Test router switching between providers."""
        router = LLMRouter()
        
        # Import to check available models
        from steer_llm_sdk.core.routing import MODEL_CONFIGS
        
        # Test OpenAI provider - use actual model that maps to OpenAI
        response = await router.generate(
            "Test OpenAI",
            "gpt-4o-mini",  # Use the actual model ID from MODEL_CONFIGS
            {"temperature": 0.7}
        )
        
        assert response.provider == "openai"
        
        # Test Anthropic provider - use actual model that maps to Anthropic
        # Verify the model exists and is anthropic
        assert "claude-3-haiku" in MODEL_CONFIGS
        assert MODEL_CONFIGS["claude-3-haiku"].provider == "anthropic"
        
        response = await router.generate(
            "Test Anthropic",
            "claude-3-haiku",  # Use the actual model ID from MODEL_CONFIGS
            {"temperature": 0.7}
        )
        
        assert response.provider == "anthropic"
    
    @pytest.mark.asyncio
    async def test_error_handling_no_api_key(self):
        """Test error handling when API key is missing."""
        from fastapi import HTTPException
        import os
        
        # Save original env vars
        original_openai = os.environ.get('OPENAI_API_KEY')
        original_anthropic = os.environ.get('ANTHROPIC_API_KEY')
        original_xai = os.environ.get('XAI_API_KEY')
        original_bypass = os.environ.get('STEER_SDK_BYPASS_AVAILABILITY_CHECK')
        
        try:
            # Clear all API keys and bypass
            for key in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'STEER_SDK_BYPASS_AVAILABILITY_CHECK']:
                if key in os.environ:
                    del os.environ[key]
            
            # Clear the cache to ensure fresh availability check
            from steer_llm_sdk.core.routing.selector import _model_status_cache
            _model_status_cache.clear()
            
            router = LLMRouter()
            
            # The router should raise HTTPException when model is not available
            with pytest.raises(HTTPException) as exc_info:
                await router.generate(
                    "Test",
                    "gpt-4o-mini",  # Use actual model ID
                    {}
                )
            
            # Check that the error message indicates model not available
            assert exc_info.value.status_code == 400
            assert "not available" in str(exc_info.value.detail)
            
        finally:
            # Restore original env vars
            if original_openai:
                os.environ['OPENAI_API_KEY'] = original_openai
            if original_anthropic:
                os.environ['ANTHROPIC_API_KEY'] = original_anthropic
            if original_xai:
                os.environ['XAI_API_KEY'] = original_xai
            if original_bypass:
                os.environ['STEER_SDK_BYPASS_AVAILABILITY_CHECK'] = original_bypass
    
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
            content=response1.text
        ))
        
        # Second user message
        conversation.append(ConversationMessage(
            role=ConversationRole.USER,
            content="What about Germany?"
        ))
        
        # Get second response
        response2 = await client.generate(conversation, model="GPT-4o Mini")
        
        from steer_llm_sdk.models.generation import GenerationResponse
        assert isinstance(response1, GenerationResponse)
        assert isinstance(response2, GenerationResponse)
        assert len(conversation) == 4  # System + 2 user + 1 assistant
    
    @pytest.mark.asyncio
    async def test_parameter_validation(self, mock_providers):
        """Test parameter validation."""
        from pydantic import ValidationError
        
        client = SteerLLMClient()
        
        # Test with valid temperature at the boundary
        result = await client.generate(
            "Test",
            temperature=2.0,  # Maximum valid temperature
            max_tokens=10
        )
        
        from steer_llm_sdk.models.generation import GenerationResponse
        assert isinstance(result, GenerationResponse)
        
        # Test with valid max_tokens
        result = await client.generate(
            "Test",
            max_tokens=8192  # Maximum valid tokens
        )
        
        from steer_llm_sdk.models.generation import GenerationResponse
        assert isinstance(result, GenerationResponse)
        
        # Test that invalid values raise ValidationError during normalization
        from steer_llm_sdk.core.routing import normalize_params, get_config
        from steer_llm_sdk.core.routing import MODEL_CONFIGS
        
        # Get a config that exists
        config = MODEL_CONFIGS["gpt-4o-mini"]
        
        # Invalid temperature should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            normalize_params({"temperature": 5.0}, config)
        
        # Check the error is about temperature
        assert "temperature" in str(exc_info.value)