"""Shared pytest fixtures for Steer LLM SDK tests."""

import pytest
import os
from dotenv import load_dotenv
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

# Load environment variables from .env file for tests
load_dotenv()

from steer_llm_sdk.models.generation import (
    GenerationParams,
    GenerationResponse,
    ModelConfig,
    ProviderType
)
from steer_llm_sdk.models.conversation_types import ConversationMessage, TurnRole as ConversationRole
from tests.helpers.streaming_mocks import (
    create_openai_stream, create_anthropic_stream, create_xai_stream
)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    env_vars = {
        "OPENAI_API_KEY": "test-openai-key",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "XAI_API_KEY": "test-xai-key",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def sample_generation_params():
    """Sample generation parameters."""
    return GenerationParams(
        model="test-model",
        max_tokens=100,
        temperature=0.7,
        top_p=0.95,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        stop=None
    )


@pytest.fixture
def sample_generation_response():
    """Sample generation response."""
    return GenerationResponse(
        text="This is a test response",
        model="test-model",
        usage={
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        },
        provider="test",
        finish_reason="stop"
    )


@pytest.fixture
def sample_model_config():
    """Sample model configuration."""
    return ModelConfig(
        name="test-model",
        display_name="Test Model",
        provider=ProviderType.OPENAI,
        llm_model_id="test-model-id",
        description="A test model",
        max_tokens=4096,
        temperature=0.7,
        enabled=True,
        cost_per_1k_tokens=0.001
    )


@pytest.fixture
def sample_conversation_messages():
    """Sample conversation messages."""
    return [
        ConversationMessage(
            role=ConversationRole.SYSTEM,
            content="You are a helpful assistant."
        ),
        ConversationMessage(
            role=ConversationRole.USER,
            content="What is the weather like?"
        ),
        ConversationMessage(
            role=ConversationRole.ASSISTANT,
            content="I don't have access to real-time weather data."
        )
    ]


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    client = AsyncMock()
    
    # Mock chat completions
    completion = Mock()
    completion.choices = [Mock(message=Mock(content="Test response"), finish_reason="stop")]
    # Make usage a proper object with model_dump method
    usage_mock = Mock()
    usage_mock.prompt_tokens = 10
    usage_mock.completion_tokens = 5
    usage_mock.total_tokens = 15
    usage_mock.model_dump.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15
    }
    completion.usage = usage_mock
    completion.model = "gpt-4o-mini"
    
    client.chat.completions.create = AsyncMock(return_value=completion)
    
    # Mock streaming
    chunks = ["Test", " response", " streaming"]
    
    async def create_response(**kwargs):
        if kwargs.get("stream"):
            return create_openai_stream(chunks)
        return completion
    
    client.chat.completions.create = AsyncMock(side_effect=create_response)
    
    return client


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client."""
    client = AsyncMock()
    
    # Mock message creation
    message = Mock()
    message.content = [Mock(type="text", text="Test response")]
    message.stop_reason = "end_turn"
    # Make usage a proper object with model_dump method
    usage_mock = Mock()
    usage_mock.input_tokens = 10
    usage_mock.output_tokens = 5
    usage_mock.model_dump.return_value = {
        "input_tokens": 10,
        "output_tokens": 5
    }
    message.usage = usage_mock
    
    client.messages.create = AsyncMock(return_value=message)
    
    # Mock streaming
    chunks = ["Test", " response"]
    
    async def create_response(**kwargs):
        if kwargs.get("stream"):
            return create_anthropic_stream(chunks)
        return message
    
    client.messages.create = AsyncMock(side_effect=create_response)
    
    return client


@pytest.fixture
def mock_xai_client():
    """Mock xAI client."""
    client = AsyncMock()
    
    # Mock chat creation and sampling
    chat = Mock()
    sample_result = Mock(content="Test response", finish_reason="stop")
    chat.sample = AsyncMock(return_value=sample_result)
    
    client.chat.create = AsyncMock(return_value=chat)
    
    # Mock streaming
    chunks = ["Test", " response"]
    chat.stream = lambda: create_xai_stream(chunks)
    
    return client




@pytest.fixture
def mock_providers(mock_openai_client, mock_anthropic_client, mock_xai_client):
    """Mock all provider clients."""
    # Create a flexible mock for AsyncAnthropic that accepts any kwargs
    def create_anthropic_mock(*args, **kwargs):
        return mock_anthropic_client
    
    with patch("openai.AsyncOpenAI", return_value=mock_openai_client), \
         patch("anthropic.AsyncAnthropic", side_effect=create_anthropic_mock), \
         patch("xai_sdk.AsyncClient", return_value=mock_xai_client):
        yield {
            "openai": mock_openai_client,
            "anthropic": mock_anthropic_client,
            "xai": mock_xai_client
        }


@pytest.fixture
def raw_model_configs():
    """Raw model configurations for testing."""
    return {
        "GPT-4o Mini": {
            "name": "GPT-4o Mini",
            "display_name": "GPT-4o Mini",
            "provider": "openai",
            "llm_model_id": "gpt-4o-mini",
            "description": "Fast, cost-effective model",
            "max_tokens": 4096,
            "temperature": 0.7,
            "enabled": True,
            "cost_per_1k_tokens": 0.00015
        },
        "Claude 3.5 Sonnet": {
            "name": "Claude 3.5 Sonnet",
            "display_name": "Claude 3.5 Sonnet", 
            "provider": "anthropic",
            "llm_model_id": "claude-3-5-sonnet-20241022",
            "description": "Advanced reasoning model",
            "max_tokens": 8192,
            "temperature": 0.7,
            "enabled": True,
            "cost_per_1k_tokens": 0.003
        }
    }