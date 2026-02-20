"""Unit tests for OpenAI Agents SDK adapter."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
from steer_llm_sdk.integrations.agents.base import AgentRunOptions, PreparedRun
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition, Tool
from steer_llm_sdk.streaming.manager import EventManager


class TestOpenAIAgentAdapter:
    """Test OpenAI agent adapter implementation."""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter instance."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            return OpenAIAgentAdapter()
    
    @pytest.fixture
    def basic_definition(self):
        """Create basic agent definition."""
        return AgentDefinition(
            system="You are a helpful assistant",
            user_template="Answer this: {question}",
            model="gpt-4o-mini",
            parameters={"temperature": 0.7, "max_tokens": 100}
        )
    
    @pytest.fixture
    def schema_definition(self):
        """Create agent definition with schema."""
        return AgentDefinition(
            system="You are a JSON generator",
            user_template="Generate data for: {topic}",
            model="gpt-4o-mini",
            json_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "confidence": {"type": "number"}
                },
                "required": ["answer"]
            },
            parameters={"temperature": 0.0}
        )
    
    @pytest.fixture
    def tool_definition(self):
        """Create agent definition with tools."""
        return AgentDefinition(
            system="You are a helpful assistant with tools",
            user_template="Help with: {task}",
            model="gpt-4o-mini",
            tools=[
                Tool(
                    name="calculate",
                    description="Perform calculations",
                    parameters={
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string"}
                        },
                        "required": ["expression"]
                    },
                    handler=lambda expr: eval(expr)
                )
            ]
        )
    
    def test_supports_features(self, adapter):
        """Test feature support methods."""
        assert adapter.supports_schema() is True
        assert adapter.supports_tools() is True
    
    @pytest.mark.asyncio
    async def test_prepare_basic(self, adapter, basic_definition):
        """Test basic agent preparation."""
        options = AgentRunOptions(
            runtime="openai_agents",
            deterministic=False
        )
        
        with patch.object(adapter, "_ensure_imports"):
            prepared = await adapter.prepare(basic_definition, options)
        
        assert prepared.runtime == "openai_agents"
        assert prepared.agent["system"] == "You are a helpful assistant"
        assert prepared.agent["user_template"] == "Answer this: {question}"
        assert prepared.agent["config"]["model"] == "gpt-4o-mini"
        assert prepared.agent["config"]["temperature"] == 0.7
        assert prepared.agent["config"]["max_tokens"] == 100
        assert not prepared.agent["use_responses_api"]
    
    @pytest.mark.asyncio
    async def test_prepare_with_schema(self, adapter, schema_definition):
        """Test preparation with JSON schema."""
        options = AgentRunOptions(
            runtime="openai_agents",
            strict=True
        )
        
        with patch.object(adapter, "_ensure_imports"):
            prepared = await adapter.prepare(schema_definition, options)
        
        assert prepared.agent["use_responses_api"]
        assert prepared.agent["response_format"]["type"] == "json_schema"
        assert prepared.agent["response_format"]["json_schema"]["strict"] is True
        assert prepared.agent["json_schema"] == schema_definition.json_schema
        
        # Verify response_format structure follows OpenAI format
        rf = prepared.agent["response_format"]
        assert "json_schema" in rf
        assert "name" in rf["json_schema"]
        assert "schema" in rf["json_schema"]
    
    @pytest.mark.asyncio
    async def test_prepare_deterministic(self, adapter, basic_definition):
        """Test deterministic preparation."""
        options = AgentRunOptions(
            runtime="openai_agents",
            deterministic=True,
            seed=42
        )
        
        with patch.object(adapter, "_ensure_imports"):
            prepared = await adapter.prepare(basic_definition, options)
        
        assert prepared.agent["config"]["temperature"] == 0.0
        assert prepared.agent["config"]["seed"] == 42
    
    @pytest.mark.asyncio
    async def test_prepare_with_tools(self, adapter, tool_definition):
        """Test preparation with tools."""
        options = AgentRunOptions(runtime="openai_agents")
        
        with patch.object(adapter, "_ensure_imports"):
            prepared = await adapter.prepare(tool_definition, options)
        
        assert len(prepared.agent["tools"]) == 1
        tool = prepared.agent["tools"][0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "calculate"
        assert tool["function"]["description"] == "Perform calculations"
    
    @pytest.mark.asyncio
    async def test_run_basic(self, adapter, basic_definition):
        """Test basic non-streaming run."""
        options = AgentRunOptions(runtime="openai_agents")
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test answer"), finish_reason="stop")]
        mock_response.usage = {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
        
        mock_client = Mock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        with patch.object(adapter, "_ensure_imports"):
            with patch.object(adapter, "_get_client", return_value=mock_client):
                # Mock cost calculation
                with patch("steer_llm_sdk.integrations.agents.openai.adapter.calculate_exact_cost", return_value=0.001):
                    with patch("steer_llm_sdk.integrations.agents.openai.adapter.calculate_cache_savings", return_value=0.0):
                        prepared = await adapter.prepare(basic_definition, options)
                        result = await adapter.run(prepared, {"question": "What is 2+2?"})
        
        assert result.content == "Test answer"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 5
        assert result.model == "gpt-4o-mini"
        assert result.runtime == "openai_agents"
        assert result.provider == "openai"
        assert result.status == "complete"
        assert result.cost_usd == 0.001  # exact cost - cache savings
    
    @pytest.mark.asyncio
    async def test_run_with_error(self, adapter, basic_definition):
        """Test run with error handling."""
        options = AgentRunOptions(runtime="openai_agents")
        
        mock_client = Mock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error: rate limit exceeded")
        )
        
        with patch.object(adapter, "_ensure_imports"):
            with patch.object(adapter, "_get_client", return_value=mock_client):
                prepared = await adapter.prepare(basic_definition, options)
                result = await adapter.run(prepared, {"question": "Test"})
        
        assert result.status == "error"
        assert "rate limit" in result.error
        assert result.content == ""
    
    @pytest.mark.asyncio
    async def test_ensure_imports_error(self, adapter):
        """Test import error handling."""
        with patch("builtins.__import__", side_effect=ImportError("No module named 'openai'")):
            with pytest.raises(ImportError) as exc_info:
                adapter._ensure_imports()
            
            assert "OpenAI SDK not installed" in str(exc_info.value)
            assert "pip install steer-llm-sdk[openai-agents]" in str(exc_info.value)
    
    def test_get_client_no_api_key(self, adapter):
        """Test client creation without API key."""
        adapter._api_key = None
        
        with patch.object(adapter, "_ensure_imports"):
            with pytest.raises(ValueError) as exc_info:
                adapter._get_client()
            
            assert "OpenAI API key not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_responses_api_uses_chat_completions(self, adapter, schema_definition):
        """Test that 'Responses API' actually uses chat completions with response_format."""
        options = AgentRunOptions(runtime="openai_agents")
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"answer": "42"}'), finish_reason="stop")]
        mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 5}
        
        mock_client = Mock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        with patch.object(adapter, "_ensure_imports"):
            with patch.object(adapter, "_get_client", return_value=mock_client):
                with patch("steer_llm_sdk.integrations.agents.openai.adapter.calculate_exact_cost", return_value=None):
                    prepared = await adapter.prepare(schema_definition, options)
                    await adapter.run(prepared, {"topic": "test"})
        
        # Verify chat.completions.create was called with response_format
        call_args = mock_client.chat.completions.create.call_args
        assert "response_format" in call_args[1]
        assert call_args[1]["response_format"]["type"] == "json_schema"