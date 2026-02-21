"""Unit tests for agent runtime mapping utilities."""

import pytest
from typing import Dict, Any

from steer_llm_sdk.integrations.agents.mapping import (
    map_tool_to_function_schema,
    prepare_schema_for_responses_api,
    apply_deterministic_params,
    map_token_limit_param,
    validate_tools_compatibility,
    prepare_messages_for_runtime
)
from steer_llm_sdk.agents.models.agent_definition import Tool
from steer_llm_sdk.core.capabilities import ProviderCapabilities


class TestToolMapping:
    """Test tool mapping functions."""
    
    def test_map_tool_to_function_schema_basic(self):
        """Test basic tool mapping."""
        tool = Tool(
            name="get_weather",
            description="Get weather information",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            },
            handler=lambda x: x
        )
        
        result = map_tool_to_function_schema(tool)
        
        assert result["type"] == "function"
        assert result["function"]["name"] == "get_weather"
        assert result["function"]["description"] == "Get weather information"
        assert result["function"]["parameters"]["properties"]["location"]["type"] == "string"
    
    def test_map_tool_to_function_schema_empty_params(self):
        """Test tool mapping with empty parameters."""
        tool = Tool(
            name="hello",
            description="Say hello",
            parameters={},  # Empty dict instead of None
            handler=lambda: "hello"
        )
        
        result = map_tool_to_function_schema(tool)
        
        assert result["function"]["parameters"]["type"] == "object"
        assert result["function"]["parameters"]["properties"] == {}
        assert result["function"]["parameters"]["required"] == []


class TestSchemaPreparation:
    """Test schema preparation for Responses API."""
    
    def test_prepare_schema_basic(self):
        """Test basic schema preparation."""
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"}
            },
            "required": ["answer"]
        }
        
        result = prepare_schema_for_responses_api(schema, "test_result", strict=True)
        
        assert result["type"] == "json_schema"
        assert result["json_schema"]["name"] == "test_result"
        assert result["json_schema"]["schema"]["additionalProperties"] is False
        assert result["json_schema"]["strict"] is True
    
    def test_prepare_schema_preserves_additional_properties(self):
        """Test that existing additionalProperties is preserved."""
        schema = {
            "type": "object",
            "properties": {"x": {"type": "number"}},
            "additionalProperties": True
        }
        
        result = prepare_schema_for_responses_api(schema, strict=True)
        
        assert result["json_schema"]["schema"]["additionalProperties"] is True


class TestDeterministicParams:
    """Test deterministic parameter application."""
    
    def test_apply_deterministic_params_basic(self):
        """Test basic deterministic parameter application."""
        params = {
            "temperature": 0.7,
            "top_p": 0.9,
            "presence_penalty": 0.1
        }
        capabilities = ProviderCapabilities(
            supports_temperature=True,
            deterministic_temperature_max=0.0,
            deterministic_top_p=1.0,
            supports_seed=True,
            max_context_length=4096,
            max_output_tokens=4096
        )
        
        result = apply_deterministic_params(params, "test-model", capabilities, seed=42)
        
        assert result["temperature"] == 0.0
        assert result["top_p"] == 1.0
        assert result["presence_penalty"] == 0
        assert result["seed"] == 42
    
    def test_apply_deterministic_params_no_temperature_support(self):
        """Test when model doesn't support temperature."""
        params = {"temperature": 0.7}
        capabilities = ProviderCapabilities(
            supports_temperature=False,
            max_context_length=4096,
            max_output_tokens=4096
        )
        
        result = apply_deterministic_params(params, "test-model", capabilities)
        
        assert "temperature" not in result
    
    def test_apply_deterministic_params_requires_temp_one(self):
        """Test when model requires temperature=1.0."""
        params = {"temperature": 0.5}
        capabilities = ProviderCapabilities(
            supports_temperature=True,
            requires_temperature_one=True,
            max_context_length=4096,
            max_output_tokens=4096
        )
        
        result = apply_deterministic_params(params, "test-model", capabilities)
        
        assert result["temperature"] == 1.0


class TestTokenLimitMapping:
    """Test token limit parameter mapping."""
    
    def test_map_token_limit_standard(self):
        """Test standard max_tokens mapping."""
        params = {"max_tokens": 1000}
        capabilities = ProviderCapabilities(
            uses_max_completion_tokens=False,
            uses_max_output_tokens_in_responses_api=False,
            max_context_length=4096,
            max_output_tokens=4096
        )
        
        result = map_token_limit_param(params, capabilities)
        
        assert result["max_tokens"] == 1000
        assert "max_completion_tokens" not in result
        assert "max_output_tokens" not in result
    
    def test_map_token_limit_completion_tokens(self):
        """Test max_completion_tokens mapping."""
        params = {"max_tokens": 1000}
        capabilities = ProviderCapabilities(
            uses_max_completion_tokens=True,
            max_context_length=4096,
            max_output_tokens=4096
        )
        
        result = map_token_limit_param(params, capabilities)
        
        assert result["max_completion_tokens"] == 1000
        assert "max_tokens" not in result
    
    def test_map_token_limit_responses_api(self):
        """Test Responses API token mapping."""
        params = {"max_tokens": 1000}
        capabilities = ProviderCapabilities(
            uses_max_output_tokens_in_responses_api=True,
            max_context_length=4096,
            max_output_tokens=4096
        )
        
        result = map_token_limit_param(params, capabilities, is_responses_api=True)
        
        assert result["max_output_tokens"] == 1000
        assert "max_tokens" not in result


class TestToolsValidation:
    """Test tools compatibility validation."""
    
    def test_validate_tools_unsupported(self):
        """Test validation when tools not supported."""
        tools = [
            Tool(name="tool1", description="Test", parameters={}, handler=lambda: None),
            Tool(name="tool2", description="Test", parameters={}, handler=lambda: None)
        ]
        capabilities = ProviderCapabilities(
            supports_tools=False,
            max_context_length=4096,
            max_output_tokens=4096
        )
        
        warnings = validate_tools_compatibility(tools, capabilities)
        
        assert len(warnings) == 1
        assert "does not support tools" in warnings[0]
        assert "2 tools will be ignored" in warnings[0]
    
    def test_validate_tools_missing_fields(self):
        """Test validation with missing required fields."""
        tools = [
            Tool(name="", description="Test", parameters={}, handler=lambda: None),
            Tool(name="tool2", description="", parameters={}, handler=lambda: None)
        ]
        capabilities = ProviderCapabilities(
            supports_tools=True,
            max_context_length=4096,
            max_output_tokens=4096
        )
        
        warnings = validate_tools_compatibility(tools, capabilities)
        
        assert len(warnings) == 2
        assert "missing required 'name'" in warnings[0]
        assert "missing required 'description'" in warnings[1]


class TestMessagePreparation:
    """Test message preparation for runtime."""
    
    def test_prepare_messages_standard(self):
        """Test standard message preparation."""
        messages = prepare_messages_for_runtime(
            system="You are a helpful assistant",
            user_text="Hello!",
            responses_use_instructions=False
        )
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello!"
    
    def test_prepare_messages_instructions_format(self):
        """Test instructions format for Responses API."""
        messages = prepare_messages_for_runtime(
            system="You are a helpful assistant",
            user_text="Hello!",
            responses_use_instructions=True
        )
        
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello!"