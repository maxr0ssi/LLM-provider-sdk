"""
Integration tests for agent framework components.
"""

import pytest
from typing import Dict, Any

from steer_llm_sdk.agents import (
    AgentDefinition,
    AgentOptions,
    AgentResult,
    Budget,
    ProviderCapabilities
)
from steer_llm_sdk.agents.validators.json_schema import JsonSchemaValidator
from steer_llm_sdk.core.capabilities.models import get_model_capabilities
from steer_llm_sdk.core.routing import get_capabilities


class TestAgentFrameworkIntegration:
    """Test integration between agent framework components."""
    
    def test_agent_with_model_capabilities(self):
        """Test agent definition works with model capabilities."""
        # Define an agent for GPT-5 mini
        agent = AgentDefinition(
            system="You are a data extractor",
            user_template="Extract info from: {text}",
            model="gpt-5-mini",
            json_schema={
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        )
        
        # Get capabilities for the model
        caps = get_model_capabilities(agent.model)
        
        # Verify the model supports required features
        assert caps.supports_json_schema is True
        assert caps.supports_response_format is True
        assert caps.max_output_tokens >= 1000  # Enough for extraction
    
    def test_agent_options_with_budget(self):
        """Test agent options integrate with budget constraints."""
        # Create options with budget
        budget = Budget(tokens=1000, ms=5000)
        options = AgentOptions(
            streaming=True,
            deterministic=True,
            budget=budget,
            metadata={"task": "extraction"},
            trace_id="test-123"
        )
        
        # Verify serialization works
        options_dict = options.model_dump(exclude_none=True)
        assert options_dict["budget"]["tokens"] == 1000
        assert options_dict["budget"]["ms"] == 5000
        assert "on_start" not in options_dict  # Callbacks excluded
    
    def test_result_validation_with_schema(self):
        """Test result content validation against agent schema."""
        # Define expected schema
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "score": {"type": "number", "minimum": 0, "maximum": 100}
            },
            "required": ["summary", "score"]
        }
        
        # Create agent with schema
        agent = AgentDefinition(
            system="Summarize and score",
            user_template="Analyze: {content}",
            model="gpt-4o-mini",
            json_schema=schema
        )
        
        # Simulate result
        result_content = {
            "summary": "This is a test summary",
            "score": 85.5
        }
        
        # Validate result content
        validated = JsonSchemaValidator.validate_data(result_content, agent.json_schema)
        assert validated == result_content
        
        # Create actual result
        result = AgentResult(
            content=result_content,
            usage={"prompt_tokens": 50, "completion_tokens": 20},
            model=agent.model,
            elapsed_ms=150
        )
        
        assert result.content["score"] == 85.5
    
    def test_model_capability_based_options(self):
        """Test setting options based on model capabilities."""
        models_to_test = [
            ("gpt-5-mini", True, True),      # Supports determinism
            ("claude-3-haiku-20240307", True, False),  # No seed support
            ("o4-mini", True, False),         # Special requirements
        ]
        
        for model_id, supports_streaming, supports_seed in models_to_test:
            caps = get_capabilities(model_id)
            
            # Create agent
            agent = AgentDefinition(
                system="Test agent",
                user_template="Process: {input}",
                model=model_id
            )
            
            # Set options based on capabilities
            options = AgentOptions(
                streaming=supports_streaming and caps.supports_streaming,
                deterministic=supports_seed and caps.supports_seed
            )
            
            assert options.streaming == (supports_streaming and caps.supports_streaming)
            assert options.deterministic == (supports_seed and caps.supports_seed)
    
    def test_tool_integration(self):
        """Test tool definition in agent."""
        from steer_llm_sdk.agents.models.agent_definition import Tool
        
        # Define a simple tool
        def word_count(text: str) -> Dict[str, int]:
            """Count words in text."""
            words = text.split()
            return {"count": len(words)}
        
        tool = Tool(
            name="word_count",
            description="Count words in text",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            },
            handler=word_count
        )
        
        # Create agent with tool
        agent = AgentDefinition(
            system="You can count words",
            user_template="Analyze: {text}",
            model="gpt-5-mini",
            tools=[tool]
        )
        
        # Verify tool is properly integrated
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "word_count"
        
        # Test tool execution
        result = agent.tools[0].handler("hello world test")
        assert result == {"count": 3}
    
    def test_cost_tracking_in_result(self):
        """Test cost information in agent result."""
        # Get model capabilities
        caps = get_capabilities("gpt-5-mini")
        
        # Create result with cost info
        result = AgentResult(
            content={"answer": "42"},
            usage={
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "total_tokens": 1500
            },
            model="gpt-5-mini",
            elapsed_ms=200,
            cost_usd=0.00125,  # 1000 * 0.00025 + 500 * 0.002
            cost_breakdown={
                "input_cost": 0.00025,
                "output_cost": 0.001,
                "cache_savings": 0.0
            }
        )
        
        # Verify cost tracking
        assert result.cost_usd == 0.00125
        assert result.cost_breakdown["input_cost"] == 0.00025
        assert result.cost_breakdown["output_cost"] == 0.001
        
        # Verify the model has pricing info
        assert caps.has_input_output_pricing is True
        assert caps.has_cached_pricing is True