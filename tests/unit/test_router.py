"""Unit tests for LLM router functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException

from steer_llm_sdk.llm.router import LLMRouter
from steer_llm_sdk.models.generation import (
    GenerationParams,
    GenerationResponse,
    ModelConfig,
    ProviderType
)
from steer_llm_sdk.models.conversation_types import ConversationMessage, TurnRole as ConversationRole


class TestLLMRouter:
    """Test LLM router functionality."""
    
    @pytest.fixture
    def router(self):
        """Create a router instance."""
        return LLMRouter()
    
    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider."""
        provider = Mock()
        provider.generate = AsyncMock(return_value=GenerationResponse(
            text="Test response",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            provider="test",
            finish_reason="stop"
        ))
        
        async def mock_stream():
            for chunk in ["Test", " response"]:
                yield chunk
        
        provider.generate_stream = mock_stream
        provider.is_available = Mock(return_value=True)
        return provider
    
    @pytest.mark.asyncio
    async def test_generate_simple_prompt(self, router, mock_provider):
        """Test generation with simple string prompt."""
        with patch('steer_llm_sdk.llm.registry.get_config') as mock_get_config, \
             patch('steer_llm_sdk.llm.registry.check_lightweight_availability', return_value=True), \
             patch('steer_llm_sdk.llm.registry.normalize_params') as mock_normalize:
            
            # Setup mocks
            mock_get_config.return_value = ModelConfig(
                name="test",
                display_name="Test",
                provider=ProviderType.OPENAI,
                llm_model_id="test-model",
                description="Test",
                cost_per_1k_tokens=0.001
            )
            
            mock_normalize.return_value = GenerationParams(
                model="test-model",
                max_tokens=100,
                temperature=0.7
            )
            
            router.providers[ProviderType.OPENAI] = mock_provider
            
            # Test generation
            response = await router.generate(
                "Test prompt",
                "test-model",
                {"temperature": 0.7}
            )
            
            assert response.text == "Test response"
            assert response.cost_usd == 0.000015  # 15 tokens * 0.001/1k
            mock_provider.generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_conversation_messages(self, router, mock_provider):
        """Test generation with conversation messages."""
        messages = [
            ConversationMessage(role=ConversationRole.USER, content="Hello")
        ]
        
        with patch('steer_llm_sdk.llm.registry.get_config') as mock_get_config, \
             patch('steer_llm_sdk.llm.registry.check_lightweight_availability', return_value=True), \
             patch('steer_llm_sdk.llm.registry.normalize_params') as mock_normalize:
            
            mock_get_config.return_value = ModelConfig(
                name="test",
                display_name="Test",
                provider=ProviderType.ANTHROPIC,
                llm_model_id="test-model",
                description="Test"
            )
            
            mock_normalize.return_value = GenerationParams(
                model="test-model",
                max_tokens=100
            )
            
            router.providers[ProviderType.ANTHROPIC] = mock_provider
            
            response = await router.generate(messages, "test-model", {})
            
            assert response.text == "Test response"
            mock_provider.generate.assert_called_once_with(messages, mock_normalize.return_value)
    
    @pytest.mark.asyncio
    async def test_generate_model_not_available(self, router):
        """Test generation when model is not available."""
        with patch('steer_llm_sdk.llm.registry.get_config'), \
             patch('steer_llm_sdk.llm.registry.check_lightweight_availability', return_value=False):
            
            with pytest.raises(HTTPException) as exc_info:
                await router.generate("Test", "unavailable-model", {})
            
            assert exc_info.value.status_code == 400
            assert "not available" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_generate_provider_not_implemented(self, router):
        """Test generation with unimplemented provider."""
        with patch('steer_llm_sdk.llm.registry.get_config') as mock_get_config, \
             patch('steer_llm_sdk.llm.registry.check_lightweight_availability', return_value=True), \
             patch('steer_llm_sdk.llm.registry.normalize_params'):
            
            # Create a config with invalid provider
            mock_get_config.return_value = ModelConfig(
                name="test",
                display_name="Test",
                provider="invalid_provider",  # Not in ProviderType enum
                llm_model_id="test-model",
                description="Test"
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await router.generate("Test", "test-model", {})
            
            assert exc_info.value.status_code == 500
            assert "not implemented" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_generate_provider_error(self, router):
        """Test generation when provider raises an error."""
        mock_provider = Mock()
        mock_provider.generate = AsyncMock(side_effect=Exception("Provider error"))
        
        with patch('steer_llm_sdk.llm.registry.get_config') as mock_get_config, \
             patch('steer_llm_sdk.llm.registry.check_lightweight_availability', return_value=True), \
             patch('steer_llm_sdk.llm.registry.normalize_params'):
            
            mock_get_config.return_value = ModelConfig(
                name="test",
                display_name="Test",
                provider=ProviderType.OPENAI,
                llm_model_id="test-model",
                description="Test"
            )
            
            router.providers[ProviderType.OPENAI] = mock_provider
            
            with pytest.raises(HTTPException) as exc_info:
                await router.generate("Test", "test-model", {})
            
            assert exc_info.value.status_code == 500
            assert "Generation failed" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_generate_stream(self, router, mock_provider):
        """Test streaming generation."""
        with patch('steer_llm_sdk.llm.registry.get_config') as mock_get_config, \
             patch('steer_llm_sdk.llm.registry.check_lightweight_availability', return_value=True), \
             patch('steer_llm_sdk.llm.registry.normalize_params') as mock_normalize:
            
            mock_get_config.return_value = ModelConfig(
                name="test",
                display_name="Test",
                provider=ProviderType.OPENAI,
                llm_model_id="test-model",
                description="Test"
            )
            
            mock_normalize.return_value = GenerationParams(
                model="test-model",
                max_tokens=100
            )
            
            router.providers[ProviderType.OPENAI] = mock_provider
            
            # Collect streamed chunks
            chunks = []
            async for chunk in router.generate_stream("Test", "test-model", {}):
                chunks.append(chunk)
            
            assert chunks == ["Test", " response"]
    
    def test_get_provider_status(self, router):
        """Test getting provider status."""
        # Mock providers
        for provider_type in ProviderType:
            mock_provider = Mock()
            mock_provider.is_available = Mock(return_value=provider_type == ProviderType.OPENAI)
            router.providers[provider_type] = mock_provider
        
        status = router.get_provider_status()
        
        assert isinstance(status, dict)
        assert status[ProviderType.OPENAI.value] is True
        assert status[ProviderType.ANTHROPIC.value] is False
        assert status[ProviderType.XAI.value] is False
        assert status[ProviderType.LOCAL.value] is False