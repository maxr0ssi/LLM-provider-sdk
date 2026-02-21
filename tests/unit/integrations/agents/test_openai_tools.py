"""Unit tests for OpenAI Agents SDK tool mapping utilities."""

import pytest
import asyncio
from unittest.mock import Mock, patch
from typing import Any

from steer_llm_sdk.integrations.agents.openai.tools import (
    create_tool_wrapper,
    convert_tools_to_sdk_format,
    extract_tool_results,
    validate_tool_compatibility
)
from steer_llm_sdk.agents.models.agent_definition import Tool


# Mock function_tool decorator
def mock_function_tool(func):
    """Mock function_tool decorator that just returns the function."""
    func._is_function_tool = True
    return func


@pytest.fixture
def simple_tool():
    """Create a simple synchronous tool."""
    def handler(text: str, count: int = 1) -> str:
        return f"{text} x {count}"
    
    return Tool(
        name="repeat_text",
        description="Repeats text a specified number of times",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to repeat"},
                "count": {"type": "integer", "description": "Number of times", "default": 1}
            },
            "required": ["text"]
        },
        handler=handler,
        deterministic=True
    )


@pytest.fixture
def async_tool():
    """Create an async tool."""
    async def async_handler(query: str) -> str:
        await asyncio.sleep(0.01)  # Simulate async operation
        return f"Result for: {query}"
    
    return Tool(
        name="async_search",
        description="Async search operation",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        },
        handler=async_handler,
        deterministic=False
    )


@pytest.fixture
def complex_tool():
    """Create a tool with complex parameters."""
    def handler(data: dict, items: list, enabled: bool = True) -> dict:
        return {
            "processed": len(items),
            "enabled": enabled,
            "data_keys": list(data.keys())
        }
    
    return Tool(
        name="process_data",
        description="Process complex data",
        parameters={
            "type": "object",
            "properties": {
                "data": {"type": "object", "description": "Data to process"},
                "items": {"type": "array", "description": "List of items"},
                "enabled": {"type": "boolean", "default": True}
            },
            "required": ["data", "items"]
        },
        handler=handler,
        deterministic=True
    )


class TestCreateToolWrapper:
    """Test create_tool_wrapper function."""
    
    def test_sync_tool_wrapper(self, simple_tool):
        """Test wrapping a synchronous tool."""
        with patch('steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE', True):
            wrapper = create_tool_wrapper(simple_tool)
            
            # Check function metadata
            assert wrapper.__name__ == "repeat_text"
            assert wrapper.__doc__ == "Repeats text a specified number of times"
            
            # Check annotations
            assert "text" in wrapper.__annotations__
            assert "count" in wrapper.__annotations__
            assert wrapper.__annotations__["text"] == str
            assert wrapper.__annotations__["count"] == int
            assert wrapper.__annotations__["return"] == Any
            
            # Test execution
            result = wrapper(text="hello", count=3)
            assert result == "hello x 3"
            
            # Test with extra parameters (should be filtered)
            result = wrapper(text="test", count=2, extra="ignored")
            assert result == "test x 2"
    
    @pytest.mark.asyncio
    async def test_async_tool_wrapper(self, async_tool):
        """Test wrapping an async tool."""
        with patch('steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE', True):
            wrapper = create_tool_wrapper(async_tool)
            
            # Check it's async
            assert asyncio.iscoroutinefunction(wrapper)
            
            # Test execution
            result = await wrapper(query="test query")
            assert result == "Result for: test query"
    
    def test_complex_types_mapping(self, complex_tool):
        """Test parameter type mapping for complex types."""
        with patch('steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE', True):
            wrapper = create_tool_wrapper(complex_tool)
            
            # Check type annotations
            assert wrapper.__annotations__["data"] == dict
            assert wrapper.__annotations__["items"] == list
            assert wrapper.__annotations__["enabled"] == bool
            
            # Test execution
            result = wrapper(
                data={"key": "value"},
                items=[1, 2, 3],
                enabled=False
            )
            assert result["processed"] == 3
            assert result["enabled"] is False
            assert result["data_keys"] == ["key"]
    
    def test_wrapper_without_sdk(self, simple_tool):
        """Test that wrapper raises error when SDK not available."""
        with patch('steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE', False):
            with pytest.raises(ImportError, match="OpenAI Agents SDK not available"):
                create_tool_wrapper(simple_tool)


class TestConvertToolsToSdkFormat:
    """Test convert_tools_to_sdk_format function."""
    
    def test_convert_multiple_tools(self, simple_tool, async_tool, complex_tool):
        """Test converting multiple tools to SDK format."""
        with patch('steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE', True):
            with patch('steer_llm_sdk.integrations.agents.openai.tools.function_tool', mock_function_tool):
                tools = [simple_tool, async_tool, complex_tool]
                sdk_tools = convert_tools_to_sdk_format(tools)
                
                assert len(sdk_tools) == 3
                
                # Check that function_tool decorator was applied
                for sdk_tool in sdk_tools:
                    assert hasattr(sdk_tool, '_is_function_tool')
                    assert hasattr(sdk_tool, '_original_tool')
                
                # Check names are preserved
                assert sdk_tools[0].__name__ == "repeat_text"
                assert sdk_tools[1].__name__ == "async_search"
                assert sdk_tools[2].__name__ == "process_data"
    
    def test_convert_empty_list(self):
        """Test converting empty tool list."""
        with patch('steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE', True):
            sdk_tools = convert_tools_to_sdk_format([])
            assert sdk_tools == []
    
    def test_convert_without_sdk(self, simple_tool):
        """Test that conversion raises error when SDK not available."""
        with patch('steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE', False):
            with pytest.raises(ImportError, match="OpenAI Agents SDK not available"):
                convert_tools_to_sdk_format([simple_tool])


class TestExtractToolResults:
    """Test extract_tool_results function."""
    
    def test_extract_with_tool_calls(self):
        """Test extracting tool results from SDK result."""
        # Mock SDK result with tool calls
        mock_call1 = Mock()
        mock_call1.name = "tool1"
        mock_call1.result = "result1"
        
        mock_call2 = Mock()
        mock_call2.name = "tool2"
        mock_call2.result = "result2"
        
        mock_result = Mock()
        mock_result.tool_calls = [mock_call1, mock_call2]
        
        tool_info = extract_tool_results(mock_result)
        
        assert tool_info["tools_called"] == ["tool1", "tool2"]
        assert tool_info["tool_results"]["tool1"] == "result1"
        assert tool_info["tool_results"]["tool2"] == "result2"
    
    def test_extract_without_tool_calls(self):
        """Test extracting when no tool calls present."""
        mock_result = Mock(spec=[])  # No tool_calls attribute
        
        tool_info = extract_tool_results(mock_result)
        
        assert tool_info["tools_called"] == []
        assert tool_info["tool_results"] == {}
    
    def test_extract_with_missing_attributes(self):
        """Test extraction with partially missing attributes."""
        mock_call1 = Mock(spec=["name"])  # No result attribute
        mock_call1.name = "unknown"
        
        mock_call2 = Mock()
        mock_call2.name = "tool2"
        mock_call2.result = "result2"
        
        mock_result = Mock()
        mock_result.tool_calls = [mock_call1, mock_call2]
        
        tool_info = extract_tool_results(mock_result)
        
        assert "unknown" in tool_info["tools_called"]
        assert "tool2" in tool_info["tools_called"]
        assert "tool2" in tool_info["tool_results"]
        assert "unknown" not in tool_info["tool_results"]  # No result for unknown


class TestValidateToolCompatibility:
    """Test validate_tool_compatibility function."""
    
    def test_valid_tool(self, simple_tool):
        """Test validation of a properly configured tool."""
        warnings = validate_tool_compatibility(simple_tool)
        assert warnings == []
    
    def test_non_callable_handler(self, simple_tool):
        """Test validation with non-callable handler."""
        simple_tool.handler = "not a function"
        warnings = validate_tool_compatibility(simple_tool)
        
        assert len(warnings) == 1
        assert "not callable" in warnings[0]
    
    def test_invalid_parameters(self, simple_tool):
        """Test validation with invalid parameter schema."""
        simple_tool.parameters = "not a dict"
        warnings = validate_tool_compatibility(simple_tool)
        
        assert len(warnings) == 1
        assert "must be a dictionary" in warnings[0]
    
    def test_missing_properties(self, simple_tool):
        """Test validation with missing properties field."""
        simple_tool.parameters = {"type": "object"}  # No properties
        warnings = validate_tool_compatibility(simple_tool)
        
        assert len(warnings) == 1
        assert "missing 'properties'" in warnings[0]
    
    def test_missing_description(self, simple_tool):
        """Test validation with missing description."""
        simple_tool.description = ""
        warnings = validate_tool_compatibility(simple_tool)
        
        assert len(warnings) == 1
        assert "missing description" in warnings[0]
    
    def test_non_deterministic_tool(self, async_tool):
        """Test validation warning for non-deterministic tool."""
        warnings = validate_tool_compatibility(async_tool)
        
        assert len(warnings) == 1
        assert "non-deterministic" in warnings[0]
        assert "reproducibility" in warnings[0]
    
    def test_multiple_issues(self):
        """Test validation with multiple issues."""
        # Create a tool with valid structure first
        def dummy_handler():
            pass
            
        bad_tool = Tool(
            name="bad_tool",
            description="",  # Missing description
            parameters={"properties": {}},  # Valid dict
            handler=dummy_handler,  # Valid callable
            deterministic=False  # Non-deterministic
        )
        
        # Now break it after creation
        bad_tool.parameters = "invalid"  # Make params invalid
        bad_tool.handler = "not callable"  # Make handler invalid
        
        warnings = validate_tool_compatibility(bad_tool)
        
        assert len(warnings) == 4
        assert any("not callable" in w for w in warnings)
        assert any("must be a dictionary" in w for w in warnings)
        assert any("missing description" in w for w in warnings)
        assert any("non-deterministic" in w for w in warnings)