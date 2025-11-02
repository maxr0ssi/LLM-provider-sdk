"""Tool mapping utilities for OpenAI Agents SDK.

This module provides utilities to convert our Tool model to OpenAI SDK
function_tool format, handling parameter schemas and async functions.
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, List
from functools import wraps

from ....agents.models.agent_definition import Tool

# Lazy import for optional dependency
try:
    from agents import function_tool
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    function_tool = None


def create_tool_wrapper(tool: Tool) -> Callable:
    """Create a properly annotated wrapper function for a tool.
    
    The OpenAI Agents SDK's function_tool decorator extracts parameter
    information from function annotations. This creates a wrapper with
    proper annotations based on our Tool schema.
    
    Args:
        tool: Our Tool model with name, description, parameters, and handler
        
    Returns:
        A wrapped function ready for function_tool decoration
    """
    if not AGENTS_SDK_AVAILABLE:
        raise ImportError("OpenAI Agents SDK not available")
    
    handler = tool.handler
    is_async = asyncio.iscoroutinefunction(handler)

    # Extract parameter information from schema
    param_info = {}
    required_params = set()

    if "properties" in tool.parameters:
        param_info = tool.parameters["properties"]
    if "required" in tool.parameters:
        required_params = set(tool.parameters["required"])

    # Create wrapper based on sync/async nature
    # Use inspect to create proper function signature dynamically
    import inspect
    from typing import Optional

    # Build parameter list for signature
    sig_params = []
    for param_name, param_schema in param_info.items():
        # Map JSON schema types to Python types
        param_type = Any
        if "type" in param_schema:
            type_mapping = {
                "string": str,
                "number": float,
                "integer": int,
                "boolean": bool,
                "array": list,
                "object": dict
            }
            param_type = type_mapping.get(param_schema["type"], Any)

        # Create parameter with or without default
        has_default = "default" in param_schema or param_name not in required_params
        if has_default:
            default_value = param_schema.get("default", None)
            sig_params.append(inspect.Parameter(
                param_name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default_value,
                annotation=param_type if param_type != Any else Optional[Any]
            ))
        else:
            sig_params.append(inspect.Parameter(
                param_name,
                inspect.Parameter.KEYWORD_ONLY,
                annotation=param_type
            ))

    # Create wrapper based on sync/async nature
    if is_async:
        async def wrapper(**kwargs):
            # Filter out any extra parameters not in schema
            filtered_kwargs = {
                k: v for k, v in kwargs.items()
                if k in param_info
            }
            return await handler(**filtered_kwargs)
    else:
        def wrapper(**kwargs):
            # Filter out any extra parameters not in schema
            filtered_kwargs = {
                k: v for k, v in kwargs.items()
                if k in param_info
            }
            return handler(**filtered_kwargs)

    # Apply signature to wrapper
    wrapper.__signature__ = inspect.Signature(parameters=sig_params, return_annotation=Any)
    
    # Set function metadata
    wrapper.__name__ = tool.name
    wrapper.__doc__ = tool.description

    return wrapper


def convert_tools_to_sdk_format(tools: List[Tool]) -> List[Callable]:
    """Convert a list of our Tool models to OpenAI SDK function tools.
    
    Args:
        tools: List of our Tool models
        
    Returns:
        List of decorated functions ready for OpenAI SDK
    """
    if not AGENTS_SDK_AVAILABLE:
        raise ImportError("OpenAI Agents SDK not available")
    
    sdk_tools = []
    
    for tool in tools:
        # Create wrapper function
        wrapper = create_tool_wrapper(tool)

        # Apply function_tool decorator
        decorated = function_tool(wrapper)

        # Restore function name and docstring after decoration
        # (function_tool may override these)
        decorated.__name__ = tool.name
        decorated.__doc__ = tool.description

        # Store metadata for debugging
        decorated._original_tool = tool

        sdk_tools.append(decorated)
    
    return sdk_tools


def extract_tool_results(sdk_result: Any) -> Dict[str, Any]:
    """Extract tool execution information from SDK result.
    
    Args:
        sdk_result: Result object from OpenAI SDK Runner
        
    Returns:
        Dictionary with tool execution details
    """
    tool_info = {
        "tools_called": [],
        "tool_results": {}
    }
    
    # Extract tool call information if available
    if hasattr(sdk_result, "tool_calls") and sdk_result.tool_calls:
        # Handle both list and Mock object
        tool_calls = sdk_result.tool_calls
        if hasattr(tool_calls, '__iter__'):
            for call in tool_calls:
                tool_name = getattr(call, "name", "unknown")
                tool_info["tools_called"].append(tool_name)
                
                if hasattr(call, "result"):
                    tool_info["tool_results"][tool_name] = call.result
    
    return tool_info


def validate_tool_compatibility(tool: Tool) -> List[str]:
    """Validate that a tool is compatible with OpenAI Agents SDK.
    
    Args:
        tool: Tool to validate
        
    Returns:
        List of validation warnings (empty if fully compatible)
    """
    warnings = []
    
    # Check handler is callable
    if not callable(tool.handler):
        warnings.append(f"Tool '{tool.name}' handler is not callable")
    
    # Check parameter schema
    if not isinstance(tool.parameters, dict):
        warnings.append(f"Tool '{tool.name}' parameters must be a dictionary")
    elif "properties" not in tool.parameters:
        warnings.append(f"Tool '{tool.name}' parameters missing 'properties' field")
    
    # Check description
    if not tool.description:
        warnings.append(f"Tool '{tool.name}' missing description")
    
    # Warn about non-deterministic tools
    if not tool.deterministic:
        warnings.append(
            f"Tool '{tool.name}' is marked as non-deterministic. "
            "This may affect reproducibility."
        )
    
    return warnings