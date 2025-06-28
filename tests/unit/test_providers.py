"""Unit tests for individual LLM providers."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import os

from steer_llm_sdk.llm.providers.openai import OpenAIProvider
from steer_llm_sdk.llm.providers.anthropic import AnthropicProvider
from steer_llm_sdk.llm.providers.xai import XAIProvider
from steer_llm_sdk.models.generation import GenerationParams
from steer_llm_sdk.models.conversation_types import ConversationMessage, TurnRole as ConversationRole


class TestOpenAIProvider:
    """Test OpenAI provider."""
    
    @pytest.fixture
    def provider(self):
        """Create OpenAI provider instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            return OpenAIProvider()
    
    @pytest.mark.asyncio
    async def test_generate_simple_prompt(self, provider, mock_openai_client):
        """Test generation with simple prompt."""
        provider._client = mock_openai_client
        
        params = GenerationParams(
            model="gpt-4o-mini",
            max_tokens=100,
            temperature=0.7
        )
        
        response = await provider.generate("Test prompt", params)
        
        assert response.text == "Test response"
        assert response.model == "gpt-4o-mini"
        assert response.usage["total_tokens"] == 15
        assert response.provider == "openai"
        assert response.finish_reason == "stop"
    
    @pytest.mark.asyncio
    async def test_generate_conversation(self, provider, mock_openai_client):
        """Test generation with conversation messages."""
        provider._client = mock_openai_client
        
        messages = [
            ConversationMessage(role=ConversationRole.SYSTEM, content="You are helpful"),
            ConversationMessage(role=ConversationRole.USER, content="Hello")
        ]
        
        params = GenerationParams(model="gpt-4o-mini", max_tokens=50)
        
        response = await provider.generate(messages, params)
        
        assert response.text == "Test response"
        
        # Verify messages were formatted correctly
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs["messages"][0]["role"] == "system"
        assert call_args.kwargs["messages"][0]["content"] == "You are helpful"
        assert call_args.kwargs["messages"][1]["role"] == "user"
        assert call_args.kwargs["messages"][1]["content"] == "Hello"
    
    @pytest.mark.asyncio
    async def test_generate_stream(self, provider, mock_openai_client):
        """Test streaming generation."""
        provider._client = mock_openai_client
        
        params = GenerationParams(model="gpt-4o-mini", max_tokens=100)
        
        chunks = []
        async for chunk in provider.generate_stream("Test", params):
            chunks.append(chunk)
        
        assert chunks == ["Test", " response", " streaming"]
    
    def test_is_available_with_key(self, provider):
        """Test availability check with API key."""
        assert provider.is_available() is True
    
    def test_is_available_without_key(self):
        """Test availability check without API key."""
        with patch.dict('os.environ', {}, clear=True):
            provider = OpenAIProvider()
            assert provider.is_available() is False


class TestAnthropicProvider:
    """Test Anthropic provider."""
    
    @pytest.fixture
    def provider(self):
        """Create Anthropic provider instance."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            return AnthropicProvider()
    
    @pytest.mark.asyncio
    async def test_generate_simple_prompt(self, provider, mock_anthropic_client):
        """Test generation with simple prompt."""
        provider._client = mock_anthropic_client
        
        params = GenerationParams(
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,
            temperature=0.5
        )
        
        response = await provider.generate("Test prompt", params)
        
        assert response.text == "Test response"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 5
        assert response.provider == "anthropic"
        assert response.finish_reason == "end_turn"
    
    @pytest.mark.asyncio
    async def test_generate_conversation(self, provider, mock_anthropic_client):
        """Test generation with conversation messages."""
        provider._client = mock_anthropic_client
        
        messages = [
            ConversationMessage(role=ConversationRole.USER, content="What's 2+2?"),
            ConversationMessage(role=ConversationRole.ASSISTANT, content="4"),
            ConversationMessage(role=ConversationRole.USER, content="What's 3+3?")
        ]
        
        params = GenerationParams(model="claude-3-5-sonnet-20241022", max_tokens=50)
        
        response = await provider.generate(messages, params)
        
        assert response.text == "Test response"
        
        # Verify messages were formatted correctly
        call_args = mock_anthropic_client.messages.create.call_args
        assert len(call_args.kwargs["messages"]) == 3
        assert call_args.kwargs["messages"][0]["role"] == "user"
        assert call_args.kwargs["messages"][1]["role"] == "assistant"
        assert call_args.kwargs["messages"][2]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_generate_stream(self, provider, mock_anthropic_client):
        """Test streaming generation."""
        provider._client = mock_anthropic_client
        
        params = GenerationParams(model="claude-3-5-sonnet-20241022", max_tokens=100)
        
        chunks = []
        async for chunk in provider.generate_stream("Test", params):
            chunks.append(chunk)
        
        assert chunks == ["Test", " response"]
    
    def test_is_available_with_key(self, provider):
        """Test availability check with API key."""
        assert provider.is_available() is True
    
    def test_is_available_without_key(self):
        """Test availability check without API key."""
        with patch.dict('os.environ', {}, clear=True):
            provider = AnthropicProvider()
            assert provider.is_available() is False


class TestXAIProvider:
    """Test xAI provider."""
    @pytest.fixture
    def provider(self):
        """Create xAI provider instance."""
        with patch.dict('os.environ', {'XAI_API_KEY': 'test-key'}):
            return XAIProvider()
        
    @pytest.mark.asyncio
    async def test_generate_simple_prompt(self, provider, mock_xai_client):
        """Test generation with simple prompt."""
        provider._client = mock_xai_client
        
        params = GenerationParams(
            model="grok-beta",
            max_tokens=100,
            temperature=0.8
        )
        
        response = await provider.generate("Test prompt", params)
        
        assert response.text == "Test response"
        assert response.provider == "xai"
        # xAI doesn't provide usage stats - usage dict is empty
        assert response.usage == {}
    
    @pytest.mark.asyncio
    async def test_generate_conversation(self, provider, mock_xai_client):
        """Test generation with conversation messages."""
        provider._client = mock_xai_client
        
        messages = [
            ConversationMessage(role=ConversationRole.SYSTEM, content="Be helpful"),
            ConversationMessage(role=ConversationRole.USER, content="Hello")
        ]
        
        params = GenerationParams(model="grok-beta", max_tokens=50)
        
        response = await provider.generate(messages, params)
        
        assert response.text == "Test response"
    
    @pytest.mark.asyncio
    async def test_generate_stream(self, provider, mock_xai_client):
        """Test streaming generation."""
        provider._client = mock_xai_client
        
        params = GenerationParams(model="grok-beta", max_tokens=100)
        
        chunks = []
        async for chunk in provider.generate_stream("Test", params):
            chunks.append(chunk)
        
        assert chunks == ["Test", " response"]
