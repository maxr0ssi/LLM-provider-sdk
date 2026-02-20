"""Simplified unit tests for OpenAI Agents SDK adapter.

This version uses comprehensive mocking to avoid SDK dependency issues.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Dict

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


@pytest.fixture
def mock_openai_sdk():
    """Mock the entire OpenAI Agents SDK."""
    with patch('steer_llm_sdk.integrations.agents.openai.adapter.AGENTS_SDK_AVAILABLE', True):
        with patch('steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE', True):
            # Mock Agent class
            mock_agent = Mock()
            mock_agent.name = "Assistant"
            mock_agent.guardrails = []
            
            # Mock Runner class
            mock_runner = Mock()
            mock_result = Mock()
            mock_result.final_output = "Test response"
            mock_result.usage = {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
            mock_result.tool_calls = []  # No tool calls in basic test
            mock_runner.run_sync.return_value = mock_result
            
            # Mock streaming with correct SDK event types
            async def mock_run_streamed(agent, input_text):
                # Emit raw_response_event with content
                mock_choice = Mock()
                mock_delta = Mock()
                mock_delta.content = "Test "
                mock_choice.delta = mock_delta
                mock_data = Mock()
                mock_data.choices = [mock_choice]
                mock_data.usage = None
                yield Mock(type="raw_response_event", data=mock_data)
                
                # Second content chunk
                mock_choice2 = Mock()
                mock_delta2 = Mock()
                mock_delta2.content = "response"
                mock_choice2.delta = mock_delta2
                mock_data2 = Mock()
                mock_data2.choices = [mock_choice2]
                mock_data2.usage = None
                yield Mock(type="raw_response_event", data=mock_data2)
                
                # Final event with usage
                mock_data3 = Mock()
                mock_data3.choices = []
                mock_data3.usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
                yield Mock(type="raw_response_event", data=mock_data3)
            
            mock_runner.run_streamed = mock_run_streamed
            
            # Mock function_tool decorator
            def mock_function_tool(func):
                func._is_tool = True
                return func
            
            # Mock GuardrailFunctionOutput
            class MockGuardrailOutput:
                def __init__(self, output, should_block, error_message=None):
                    self.output = output
                    self.should_block = should_block
                    self.error_message = error_message
            
            # Mock Agent constructor to set guardrails properly
            def mock_agent_constructor(name, instructions, tools=None, model_settings=None, guardrails=None):
                mock_agent.name = name
                mock_agent.instructions = instructions
                mock_agent.tools = tools or []
                mock_agent.model_settings = model_settings or {}
                mock_agent.guardrails = guardrails or []
                return mock_agent
            
            with patch('steer_llm_sdk.integrations.agents.openai.adapter.Agent', side_effect=mock_agent_constructor):
                with patch('steer_llm_sdk.integrations.agents.openai.adapter.Runner', mock_runner):
                    with patch('steer_llm_sdk.integrations.agents.openai.adapter.function_tool', mock_function_tool):
                        with patch('steer_llm_sdk.integrations.agents.openai.adapter.GuardrailFunctionOutput', MockGuardrailOutput):
                            with patch('steer_llm_sdk.integrations.agents.openai.tools.function_tool', mock_function_tool):
                                yield {
                                    'agent': mock_agent,
                                    'runner': mock_runner,
                                    'function_tool': mock_function_tool,
                                    'guardrail_output': MockGuardrailOutput
                                }


@pytest.fixture
def sample_definition():
    """Create a sample agent definition."""
    def test_handler(arg: str) -> str:
        return f"Handled: {arg}"
    
    return AgentDefinition(
        system="You are a helpful assistant.",
        user_template="Help with: {query}",
        model="gpt-4",
        parameters={"temperature": 0.7, "max_tokens": 100},
        tools=[
            Tool(
                name="test_tool",
                description="A test tool",
                parameters={
                    "type": "object",
                    "properties": {"arg": {"type": "string"}},
                    "required": ["arg"]
                },
                handler=test_handler,
                deterministic=True
            )
        ]
    )


@pytest.fixture
def mock_env():
    """Mock environment with API key."""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        yield


@pytest.fixture
def mock_capabilities():
    """Mock model capabilities."""
    # Create a mock object with attributes
    capabilities = Mock()
    capabilities.supports_seed = True
    capabilities.supports_json_schema = True
    capabilities.supports_temperature = True
    capabilities.temperature_range = [0, 2]
    capabilities.uses_max_completion_tokens = False
    capabilities.uses_max_output_tokens_in_responses_api = False
    
    with patch('steer_llm_sdk.integrations.agents.openai.adapter.get_capabilities_for_model', return_value=capabilities):
        yield capabilities


@pytest.fixture
def mock_normalize():
    """Mock parameter normalization."""
    def normalize_side_effect(params, model, provider, capabilities):
        return {
            "temperature": min(params.temperature, 1.0),
            "max_tokens": params.max_tokens
        }
    
    with patch('steer_llm_sdk.integrations.agents.openai.adapter.normalize_params', side_effect=normalize_side_effect):
        yield


@pytest.fixture
def mock_cost():
    """Mock cost calculation."""
    # calculate_exact_cost returns a float, not a dict
    cost_usd = 0.001
    with patch('steer_llm_sdk.integrations.agents.openai.adapter.calculate_exact_cost', return_value=cost_usd):
        yield cost_usd


class TestOpenAIAgentAdapterSimple:
    """Simplified tests with comprehensive mocking."""
    
    def test_adapter_creation(self, mock_env):
        """Test adapter can be created with mocked SDK."""
        from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
        
        with patch('steer_llm_sdk.integrations.agents.openai.adapter.AGENTS_SDK_AVAILABLE', True):
            adapter = OpenAIAgentAdapter()
            assert adapter.supports_schema()
            assert adapter.supports_tools()
    
    @pytest.mark.asyncio
    async def test_prepare_agent(self, mock_env, mock_openai_sdk, mock_capabilities, mock_normalize, sample_definition):
        """Test agent preparation."""
        from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
        
        adapter = OpenAIAgentAdapter()
        options = AgentRunOptions(
            runtime="openai_agents",
            streaming=False,
            deterministic=True,
            seed=42
        )
        
        prepared = await adapter.prepare(sample_definition, options)
        
        assert prepared.runtime == "openai_agents"
        assert prepared.agent == mock_openai_sdk['agent']
        assert prepared.config["model"] == "gpt-4"
        assert "normalized_params" in prepared.config
        assert prepared.metadata["capabilities"] == mock_capabilities
    
    @pytest.mark.asyncio
    async def test_run_non_streaming(self, mock_env, mock_openai_sdk, mock_capabilities, mock_normalize, mock_cost, sample_definition):
        """Test non-streaming execution."""
        from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
        
        adapter = OpenAIAgentAdapter()
        options = AgentRunOptions(runtime="openai_agents", streaming=False)
        
        prepared = await adapter.prepare(sample_definition, options)
        result = await adapter.run(prepared, {"query": "test"})
        
        assert result.content == "Test response"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 20
        assert result.model == "gpt-4"
        assert result.runtime == "openai_agents"
        assert result.cost_usd == mock_cost
        
        # Verify Runner.run_sync was called
        mock_openai_sdk['runner'].run_sync.assert_called()
    
    @pytest.mark.asyncio
    async def test_run_streaming(self, mock_env, mock_openai_sdk, mock_capabilities, mock_normalize, mock_cost, sample_definition):
        """Test streaming execution."""
        from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
        
        adapter = OpenAIAgentAdapter()
        options = AgentRunOptions(runtime="openai_agents", streaming=True)
        
        prepared = await adapter.prepare(sample_definition, options)
        
        # Mock event manager
        events = []
        event_manager = Mock(spec=EventManager)
        
        async def capture_event(event):
            events.append(event)
        
        event_manager.emit_event = AsyncMock(side_effect=capture_event)
        
        # Run streaming
        async for _ in adapter.run_stream(prepared, {"query": "test"}, event_manager):
            pass
        
        # Verify events were emitted
        assert len(events) > 0
        
        # Check event types
        event_types = [type(e).__name__ for e in events]
        assert "StreamStartEvent" in event_types
        assert "StreamDeltaEvent" in event_types
        assert "StreamUsageEvent" in event_types
        assert "StreamCompleteEvent" in event_types
        
        # Check content
        delta_events = [e for e in events if isinstance(e, StreamDeltaEvent)]
        content = "".join(e.delta for e in delta_events if e.delta)
        assert content == "Test response"
    
    @pytest.mark.asyncio
    async def test_json_schema_guardrail(self, mock_env, mock_openai_sdk, mock_capabilities, mock_normalize):
        """Test JSON schema validation via guardrails."""
        from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
        
        definition = AgentDefinition(
            system="Test",
            user_template="{input}",
            model="gpt-4",
            json_schema={
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "additionalProperties": False
            }
        )
        
        adapter = OpenAIAgentAdapter()
        options = AgentRunOptions(runtime="openai_agents", strict=True)
        
        prepared = await adapter.prepare(definition, options)
        
        # Check that guardrails were added
        assert len(prepared.agent.guardrails) == 1
        
        # Test the guardrail function
        guardrail = prepared.agent.guardrails[0]
        
        # Valid JSON
        valid_result = await guardrail(None, None, '{"answer": "test"}')
        assert not valid_result.should_block
        
        # Invalid JSON
        invalid_result = await guardrail(None, None, '{"wrong": "field"}')
        assert invalid_result.should_block
    
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_env, mock_openai_sdk, mock_capabilities, mock_normalize):
        """Test error mapping."""
        from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
        
        # Make runner raise an error
        mock_openai_sdk['runner'].run_sync.side_effect = Exception("Rate limit exceeded")
        
        adapter = OpenAIAgentAdapter()
        options = AgentRunOptions(runtime="openai_agents")
        
        definition = AgentDefinition(
            system="Test",
            user_template="{input}",
            model="gpt-4"
        )
        
        prepared = await adapter.prepare(definition, options)
        
        with pytest.raises(Exception) as exc_info:
            await adapter.run(prepared, {"input": "test"})
        
        assert "Rate limit" in str(exc_info.value)