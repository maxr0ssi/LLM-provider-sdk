"""
Unit tests for agent definition models.
"""

import pytest
from pydantic import ValidationError

from steer_llm_sdk.agents.models.agent_definition import (
    AgentDefinition,
    AgentResult,
    Budget,
    Tool
)
from steer_llm_sdk.agents.models.agent_options import AgentOptions


class TestBudget:
    """Test Budget model."""
    
    def test_valid_budget(self):
        """Test creating a valid budget."""
        budget = Budget(tokens=1000, ms=5000)
        assert budget.tokens == 1000
        assert budget.ms == 5000
    
    def test_optional_fields(self):
        """Test budget with optional fields."""
        budget = Budget()
        assert budget.tokens is None
        assert budget.ms is None
    
    def test_invalid_values(self):
        """Test budget with invalid values."""
        with pytest.raises(ValidationError):
            Budget(tokens=0)  # Must be >= 1
        
        with pytest.raises(ValidationError):
            Budget(ms=-100)  # Must be >= 1


class TestTool:
    """Test Tool model."""
    
    def test_valid_tool(self):
        """Test creating a valid tool."""
        def dummy_handler(x: int) -> int:
            return x * 2
        
        tool = Tool(
            name="multiply",
            description="Multiply by 2",
            parameters={"type": "integer"},
            handler=dummy_handler
        )
        assert tool.name == "multiply"
        assert tool.deterministic is True  # Default
        assert tool.handler(5) == 10
    
    def test_non_deterministic_tool(self):
        """Test tool marked as non-deterministic."""
        tool = Tool(
            name="random",
            description="Random number",
            parameters={},
            handler=lambda: 42,
            deterministic=False
        )
        assert tool.deterministic is False


class TestAgentDefinition:
    """Test AgentDefinition model."""
    
    def test_minimal_agent(self):
        """Test creating agent with minimal required fields."""
        agent = AgentDefinition(
            system="You are a helpful assistant",
            user_template="Answer: {question}",
            model="gpt-4o-mini"
        )
        assert agent.system == "You are a helpful assistant"
        assert agent.user_template == "Answer: {question}"
        assert agent.model == "gpt-4o-mini"
        assert agent.version == "1.0"  # Default
        assert agent.json_schema is None
        assert agent.tools is None
        assert agent.parameters == {}
    
    def test_agent_with_json_schema(self):
        """Test agent with JSON schema."""
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"}
            },
            "required": ["answer"]
        }
        
        agent = AgentDefinition(
            system="Extract information",
            user_template="Extract from: {text}",
            model="gpt-5-mini",
            json_schema=schema
        )
        assert agent.json_schema == schema
    
    def test_agent_with_parameters(self):
        """Test agent with custom parameters."""
        agent = AgentDefinition(
            system="Be creative",
            user_template="Write about: {topic}",
            model="gpt-4o-mini",
            parameters={"temperature": 0.9, "top_p": 0.95}
        )
        assert agent.parameters["temperature"] == 0.9
        assert agent.parameters["top_p"] == 0.95
    
    def test_agent_with_tools(self):
        """Test agent with tools."""
        tool = Tool(
            name="calculator",
            description="Basic math",
            parameters={"type": "object"},
            handler=lambda x: x
        )
        
        agent = AgentDefinition(
            system="You can do math",
            user_template="Calculate: {expression}",
            model="gpt-5-mini",
            tools=[tool]
        )
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "calculator"
    
    def test_no_extra_fields(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            AgentDefinition(
                system="Test",
                user_template="Test",
                model="gpt-4o-mini",
                extra_field="not allowed"
            )


class TestAgentOptions:
    """Test AgentOptions model."""
    
    def test_default_options(self):
        """Test default option values."""
        options = AgentOptions()
        assert options.streaming is False
        assert options.deterministic is False
        assert options.budget is None
        assert options.metadata == {}
        assert options.idempotency_key is None
        assert options.trace_id is None
    
    def test_options_with_budget(self):
        """Test options with budget."""
        budget = {"tokens": 500, "ms": 2000}
        options = AgentOptions(
            streaming=True,
            deterministic=True,
            budget=budget
        )
        assert options.streaming is True
        assert options.deterministic is True
        assert options.budget["tokens"] == 500
        assert options.budget["ms"] == 2000
    
    def test_options_with_metadata(self):
        """Test options with metadata."""
        options = AgentOptions(
            metadata={"user_id": "123", "session": "abc"},
            trace_id="trace-123"
        )
        assert options.metadata["user_id"] == "123"
        assert options.trace_id == "trace-123"
    
class TestAgentResult:
    """Test AgentResult model."""
    
    def test_complete_result(self):
        """Test a complete successful result."""
        result = AgentResult(
            content={"answer": "42"},
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            model="gpt-4o-mini",
            elapsed_ms=150,
            status="complete"
        )
        assert result.content == {"answer": "42"}
        assert result.usage["prompt_tokens"] == 10
        assert result.elapsed_ms == 150
        assert result.status == "complete"
        assert result.error is None
    
    def test_result_with_cost(self):
        """Test result with cost information."""
        result = AgentResult(
            content="Test response",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            model="gpt-5-mini",
            elapsed_ms=200,
            cost_usd=0.00015,
            cost_breakdown={
                "input_cost": 0.00010,
                "output_cost": 0.00005
            }
        )
        assert result.cost_usd == 0.00015
        assert result.cost_breakdown["input_cost"] == 0.00010
    
    def test_result_with_confidence(self):
        """Test result with confidence score."""
        result = AgentResult(
            content={"prediction": "yes"},
            usage={"total_tokens": 15},
            model="gpt-4o-mini",
            elapsed_ms=100,
            confidence=0.85
        )
        assert result.confidence == 0.85
    
    def test_partial_result(self):
        """Test a partial result with error."""
        result = AgentResult(
            content={"partial": "data"},
            usage={"prompt_tokens": 10},
            model="gpt-4o-mini",
            elapsed_ms=50,
            status="partial",
            error="Timeout exceeded"
        )
        assert result.status == "partial"
        assert result.error == "Timeout exceeded"
    
    def test_provider_metadata(self):
        """Test result with provider metadata."""
        result = AgentResult(
            content="Response",
            usage={"total_tokens": 20},
            model="claude-3-haiku",
            elapsed_ms=120,
            provider_metadata={
                "request_id": "req-123",
                "model_version": "2024-03-07"
            }
        )
        assert result.provider_metadata["request_id"] == "req-123"
    
    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed for flexibility."""
        result = AgentResult(
            content="Test",
            usage={},
            model="test",
            elapsed_ms=10,
            custom_field="allowed"
        )
        assert hasattr(result, "custom_field")
        assert result.custom_field == "allowed"