"""Unit tests for OpenAI Agents SDK adapter.

Tests the integration with the real OpenAI Agents SDK, including:
- Agent preparation with tools and guardrails
- Non-streaming execution
- Streaming with event mapping
- Error handling
- Tool execution
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Dict

from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
from steer_llm_sdk.integrations.agents.base import AgentRunOptions
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition, Tool
from steer_llm_sdk.streaming.manager import EventManager
from steer_llm_sdk.models.events import (
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)


# Mock the agents SDK if not available
try:
    from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False

    # Create mocks
    class MockAgent:
        def __init__(self, name, instructions, model=None, tools=None, model_settings=None,
                     output_guardrails=None, input_guardrails=None, **kwargs):
            self.name = name
            self.instructions = instructions
            self.model = model
            self.tools = tools or []
            self.model_settings = model_settings
            self.output_guardrails = output_guardrails or []
            self.input_guardrails = input_guardrails or []

    class MockModelSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class MockRunner:
        @staticmethod
        async def run(agent, input_text):
            result = Mock()
            result.final_output = "Test response"
            result.usage = {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
            return result

        @staticmethod
        def run_sync(agent, input_text):
            result = Mock()
            result.final_output = "Test response"
            result.usage = {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
            return result

        @staticmethod
        async def run_streamed(agent, input_text):
            # Simulate streaming events
            events = [
                Mock(type="content", content="Test "),
                Mock(type="content", content="streaming "),
                Mock(type="tool_call", tool_name="test_tool", arguments={"arg": "value"}),
                Mock(type="content", content="response"),
                Mock(type="usage", usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                })
            ]
            for event in events:
                yield event

    class MockGuardrailFunctionOutput:
        def __init__(self, output, should_block, error_message=None):
            self.output = output
            self.should_block = should_block
            self.error_message = error_message

    def mock_function_tool(func):
        """Mock function_tool decorator."""
        return func

    Agent = MockAgent
    Runner = MockRunner
    GuardrailFunctionOutput = MockGuardrailFunctionOutput
    ModelSettings = MockModelSettings
    function_tool = mock_function_tool


@pytest.fixture
def mock_env():
    """Mock environment with API key."""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        yield


@pytest.fixture
def sample_agent_definition():
    """Create a sample agent definition."""
    def test_handler(arg1: str, arg2: int = 0) -> str:
        return f"Handled: {arg1}, {arg2}"
    
    return AgentDefinition(
        system="You are a helpful assistant.",
        user_template="Please help with: {query}",
        json_schema={
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"}
            },
            "required": ["answer"],
            "additionalProperties": False
        },
        model="gpt-4",
        parameters={
            "temperature": 0.7,
            "max_tokens": 100,
            "top_p": 0.9
        },
        tools=[
            Tool(
                name="test_tool",
                description="A test tool",
                parameters={
                    "type": "object",
                    "properties": {
                        "arg1": {"type": "string"},
                        "arg2": {"type": "integer", "default": 0}
                    },
                    "required": ["arg1"]
                },
                handler=test_handler,
                deterministic=True
            )
        ]
    )


@pytest.fixture
def agent_options():
    """Create sample agent run options."""
    return AgentRunOptions(
        runtime="openai_agents",
        streaming=False,
        deterministic=True,
        seed=42,
        strict=True,
        trace_id="trace-123",
        request_id="req-456"
    )


@pytest.fixture
def adapter(mock_env):
    """Create OpenAI Agents adapter instance."""
    with patch('steer_llm_sdk.integrations.agents.openai.adapter.AGENTS_SDK_AVAILABLE', True):
        return OpenAIAgentAdapter()


class TestOpenAIAgentAdapter:
    """Test OpenAI Agents SDK adapter functionality."""
    
    def test_init_requires_sdk(self):
        """Test that adapter requires Agents SDK to be installed."""
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.AGENTS_SDK_AVAILABLE', False):
            with pytest.raises(ImportError, match="OpenAI Agents SDK not available"):
                OpenAIAgentAdapter()
    
    def test_init_requires_api_key(self):
        """Test that adapter requires OPENAI_API_KEY."""
        with patch.dict('os.environ', {}, clear=True):
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.AGENTS_SDK_AVAILABLE', True):
                with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable not set"):
                    OpenAIAgentAdapter()
    
    def test_supports_schema(self, adapter):
        """Test that adapter reports schema support."""
        assert adapter.supports_schema() is True
    
    def test_supports_tools(self, adapter):
        """Test that adapter reports tool support."""
        assert adapter.supports_tools() is True
    
    @pytest.mark.asyncio
    async def test_prepare_agent(self, adapter, sample_agent_definition, agent_options):
        """Test agent preparation with tools and guardrails."""
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent):
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.ModelSettings', MockModelSettings):
                with patch('steer_llm_sdk.integrations.agents.openai.adapter.function_tool', mock_function_tool):
                    with patch('steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE', True):
                        with patch('steer_llm_sdk.integrations.agents.openai.tools.function_tool', mock_function_tool):
                            prepared = await adapter.prepare(sample_agent_definition, agent_options)
                
                assert prepared.runtime == "openai_agents"
                assert isinstance(prepared.agent, MockAgent)
                assert prepared.agent.name == "Assistant"
                assert prepared.agent.instructions == sample_agent_definition.system
                assert prepared.config["model"] == "gpt-4"
                assert prepared.config["trace_id"] == "trace-123"
                assert prepared.config["request_id"] == "req-456"
                assert "prepare_time_ms" in prepared.metadata
    
    @pytest.mark.asyncio
    async def test_prepare_without_tools(self, adapter, agent_options):
        """Test agent preparation without tools."""
        definition = AgentDefinition(
            system="Simple assistant",
            user_template="Query: {input}",
            model="gpt-3.5-turbo",
            parameters={"temperature": 0.5}
        )


        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent):
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.ModelSettings', MockModelSettings):
                prepared = await adapter.prepare(definition, agent_options)

                assert prepared.agent.tools == []
                # Temperature is normalized to 0.0 in deterministic mode
                assert prepared.agent.model_settings.temperature == 0.0
    
    @pytest.mark.asyncio
    async def test_run_non_streaming(self, adapter, sample_agent_definition, agent_options):
        """Test non-streaming agent execution."""
        # Prepare agent
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent):
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.ModelSettings', MockModelSettings):
                with patch('steer_llm_sdk.integrations.agents.openai.adapter.function_tool', mock_function_tool):
                    prepared = await adapter.prepare(sample_agent_definition, agent_options)
        
        # Run agent
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Runner', MockRunner):
            result = await adapter.run(prepared, {"query": "test question"})
            
            assert result.content == "Test response"
            assert result.usage["prompt_tokens"] == 10
            assert result.usage["completion_tokens"] == 20
            assert result.usage["total_tokens"] == 30
            assert result.model == "gpt-4"
            assert result.provider == "openai"
            assert result.runtime == "openai_agents"
            assert result.trace_id == "trace-123"
            assert result.request_id == "req-456"
            assert result.elapsed_ms > 0
    
    @pytest.mark.asyncio
    async def test_run_with_json_output(self, adapter, sample_agent_definition, agent_options):
        """Test execution with JSON schema validation."""
        # Mock Runner to return JSON
        class MockJSONRunner:
            @staticmethod
            def run_sync(agent, input_text):
                result = Mock()
                result.final_output = '{"answer": "42", "confidence": 0.95}'
                result.usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
                return result
        
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent):
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.function_tool', mock_function_tool):
                prepared = await adapter.prepare(sample_agent_definition, agent_options)
        
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Runner', MockJSONRunner):
            result = await adapter.run(prepared, {"query": "What is the answer?"})
            
            assert isinstance(result.content, dict)
            assert result.content["answer"] == "42"
            assert result.content["confidence"] == 0.95
            assert result.final_json == {"answer": "42", "confidence": 0.95}
    
    @pytest.mark.asyncio
    async def test_run_streaming(self, adapter, sample_agent_definition):
        """Test streaming agent execution with event mapping."""
        options = AgentRunOptions(
            runtime="openai_agents",
            streaming=True,
            trace_id="trace-stream",
            request_id="req-stream"
        )
        
        # Prepare agent
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent):
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.ModelSettings', MockModelSettings):
                with patch('steer_llm_sdk.integrations.agents.openai.adapter.function_tool', mock_function_tool):
                    prepared = await adapter.prepare(sample_agent_definition, options)
        
        # Mock event manager
        events = []
        event_manager = Mock(spec=EventManager)
        
        async def capture_event(event):
            events.append(event)
        
        event_manager.emit = AsyncMock(side_effect=capture_event)
        
        # Run streaming
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Runner', MockRunner):
            async for _ in adapter.run_stream(prepared, {"query": "test"}, event_manager):
                pass
        
        # Verify events
        assert len(events) > 0
        
        # Check start event
        start_event = next(e for e in events if isinstance(e, StreamStartEvent))
        assert start_event.metadata["model"] == "gpt-4"
        assert start_event.metadata["runtime"] == "openai_agents"
        assert start_event.metadata["trace_id"] == "trace-stream"
        
        # Check delta events
        delta_events = [e for e in events if isinstance(e, StreamDeltaEvent)]
        assert len(delta_events) > 0
        
        # Check tool call event
        tool_events = [e for e in delta_events if e.metadata.get("type") == "tool_call"]
        assert len(tool_events) == 1
        assert tool_events[0].metadata["tool"] == "test_tool"
        
        # Check usage event
        usage_event = next(e for e in events if isinstance(e, StreamUsageEvent))
        assert usage_event.usage["prompt_tokens"] == 10
        assert usage_event.usage["completion_tokens"] == 20
        
        # Check complete event
        complete_event = next(e for e in events if isinstance(e, StreamCompleteEvent))
        assert complete_event.finish_reason == "stop"
        assert "cost_usd" in complete_event.metadata
        assert complete_event.metadata["tools_used"] == ["test_tool"]
    
    @pytest.mark.asyncio
    async def test_error_handling(self, adapter, sample_agent_definition, agent_options):
        """Test error handling and mapping."""
        # Prepare agent
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent):
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.ModelSettings', MockModelSettings):
                with patch('steer_llm_sdk.integrations.agents.openai.adapter.function_tool', mock_function_tool):
                    prepared = await adapter.prepare(sample_agent_definition, agent_options)
        
        # Mock Runner to raise error
        class ErrorRunner:
            @staticmethod
            def run_sync(agent, input_text):
                raise Exception("Rate limit exceeded")
        
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Runner', ErrorRunner):
            with pytest.raises(Exception) as exc_info:
                await adapter.run(prepared, {"query": "test"})
            
            # Error should be mapped
            assert "Rate limit" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, adapter, sample_agent_definition):
        """Test error handling in streaming mode."""
        options = AgentRunOptions(runtime="openai_agents", streaming=True)
        
        # Prepare agent
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent):
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.ModelSettings', MockModelSettings):
                with patch('steer_llm_sdk.integrations.agents.openai.adapter.function_tool', mock_function_tool):
                    prepared = await adapter.prepare(sample_agent_definition, options)
        
        # Mock Runner to raise error during streaming
        class ErrorStreamRunner:
            @staticmethod
            async def run_streamed(agent, input_text):
                yield Mock(type="content", content="Start")
                raise Exception("Connection timeout")
        
        event_manager = Mock(spec=EventManager)
        events = []
        
        async def capture_event(event):
            events.append(event)
        
        event_manager.emit = AsyncMock(side_effect=capture_event)
        
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Runner', ErrorStreamRunner):
            with pytest.raises(Exception):
                async for _ in adapter.run_stream(prepared, {"query": "test"}, event_manager):
                    pass
        
        # Should have error event
        error_events = [e for e in events if isinstance(e, StreamErrorEvent)]
        assert len(error_events) == 1
        assert "timeout" in error_events[0].error.lower()
    
    @pytest.mark.asyncio
    async def test_guardrail_validation(self, adapter, sample_agent_definition, agent_options):
        """Test that guardrails are properly configured for schema validation."""
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent) as mock_agent:
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.ModelSettings', MockModelSettings):
                with patch('steer_llm_sdk.integrations.agents.openai.adapter.function_tool', mock_function_tool):
                    prepared = await adapter.prepare(sample_agent_definition, agent_options)

                    # Verify guardrails were set
                    assert len(prepared.agent.output_guardrails) == 1

                    # Test the guardrail function
                    guardrail_func = prepared.agent.output_guardrails[0]
                
                # Valid JSON
                valid_result = await guardrail_func(
                    None, None, '{"answer": "test", "confidence": 0.8}'
                )
                assert not valid_result.should_block
                
                # Invalid JSON (missing required field)
                invalid_result = await guardrail_func(
                    None, None, '{"confidence": 0.8}'
                )
                assert invalid_result.should_block
                assert "validation failed" in invalid_result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_tool_mapping(self, adapter, sample_agent_definition, agent_options):
        """Test that tools are properly mapped to SDK format."""
        with patch('steer_llm_sdk.integrations.agents.openai.tools.convert_tools_to_sdk_format') as mock_convert:
            mock_convert.return_value = [Mock()]
            
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent):
                with patch('steer_llm_sdk.integrations.agents.openai.adapter.ModelSettings', MockModelSettings):
                    prepared = await adapter.prepare(sample_agent_definition, agent_options)

                    # Verify tool conversion was called
                    mock_convert.assert_called_once()
                    assert len(mock_convert.call_args[0][0]) == 1
                    assert mock_convert.call_args[0][0][0].name == "test_tool"
    
    @pytest.mark.asyncio
    async def test_parameter_normalization(self, adapter, agent_options):
        """Test that parameters are properly normalized for the model."""
        definition = AgentDefinition(
            system="Test",
            user_template="{input}",
            model="gpt-4",
            parameters={
                "temperature": 1.5,  # Should be clamped
                "max_tokens": 2000,
                "top_p": 0.95,
                "presence_penalty": 0.5
            }
        )
        
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', MockAgent):
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.ModelSettings', MockModelSettings):
                with patch('steer_llm_sdk.integrations.agents.openai.adapter.normalize_params') as mock_normalize:
                    mock_normalize.return_value = {
                        "temperature": 1.0,  # Clamped
                        "max_tokens": 2000,
                        "top_p": 0.95
                    }

                    prepared = await adapter.prepare(definition, agent_options)
                
                # Verify normalization was called
                mock_normalize.assert_called_once()

                # Check model settings - now a ModelSettings object, not dict
                assert prepared.agent.model_settings.temperature == 1.0
                assert prepared.agent.model_settings.max_tokens == 2000
                assert prepared.agent.model_settings.top_p == 0.95
                assert prepared.agent.model_settings.extra_args["seed"] == 42