"""Common mapping utilities for agent runtime adapters.

This module provides helper functions for mapping between our
normalized models and provider-specific formats.
"""

from typing import Any, Dict, List, Optional, Callable
import json

from ...agents.models.agent_definition import Tool, AgentDefinition
from ...core.capabilities import get_capabilities_for_model, ProviderCapabilities
from ...core.normalization.params import normalize_params


def map_tool_to_function_schema(tool: Tool) -> Dict[str, Any]:
    """Convert a Tool definition to OpenAI function schema format.
    
    Args:
        tool: Tool definition with name, description, parameters
        
    Returns:
        OpenAI-compatible function schema
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters if tool.parameters else {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }


def prepare_schema_for_responses_api(
    json_schema: Dict[str, Any],
    name: str = "result",
    strict: Optional[bool] = None
) -> Dict[str, Any]:
    """Prepare JSON schema for OpenAI Responses API format.
    
    Args:
        json_schema: JSON schema definition
        name: Schema name for Responses API
        strict: Whether to enable strict mode
        
    Returns:
        Responses API compatible schema configuration
    """
    # Ensure root has additionalProperties: false for strict mode
    schema_root = dict(json_schema)
    if strict and "additionalProperties" not in schema_root:
        schema_root["additionalProperties"] = False
    
    config = {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": schema_root
        }
    }
    
    if strict is not None:
        config["json_schema"]["strict"] = strict
    
    return config


def apply_deterministic_params(
    params: Dict[str, Any],
    model: str,
    capabilities: ProviderCapabilities,
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """Apply deterministic parameter constraints based on capabilities.
    
    Args:
        params: Model parameters
        model: Model ID
        capabilities: Model capabilities
        seed: Optional seed for determinism
        
    Returns:
        Modified parameters with deterministic settings
    """
    result = dict(params)
    
    # Apply temperature constraints
    if capabilities.supports_temperature:
        if capabilities.requires_temperature_one:
            result["temperature"] = 1.0
        else:
            result["temperature"] = min(
                result.get("temperature", 0.0),
                capabilities.deterministic_temperature_max
            )
    elif "temperature" in result:
        # Remove temperature if not supported
        del result["temperature"]
    
    # Apply top_p constraint
    if "top_p" in result:
        result["top_p"] = capabilities.deterministic_top_p
    
    # Apply seed if supported
    if seed is not None and capabilities.supports_seed:
        result["seed"] = seed
    
    # Ensure no sampling parameters that increase randomness
    for param in ["presence_penalty", "frequency_penalty"]:
        if param in result and result[param] > 0:
            result[param] = 0
    
    return result


def map_token_limit_param(
    params: Dict[str, Any],
    capabilities: ProviderCapabilities,
    is_responses_api: bool = False
) -> Dict[str, Any]:
    """Map token limit parameter based on model capabilities.
    
    Args:
        params: Model parameters
        capabilities: Model capabilities
        is_responses_api: Whether this is for Responses API
        
    Returns:
        Modified parameters with correct token field
    """
    result = dict(params)
    
    # Get the token limit value
    token_limit = None
    for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
        if field in result:
            token_limit = result.pop(field)
            break
    
    if token_limit is not None:
        # Determine correct field name
        if is_responses_api and capabilities.uses_max_output_tokens_in_responses_api:
            result["max_output_tokens"] = token_limit
        elif capabilities.uses_max_completion_tokens:
            result["max_completion_tokens"] = token_limit
        else:
            result["max_tokens"] = token_limit
    
    return result


def extract_provider_metadata(response: Any, provider: str) -> Dict[str, Any]:
    """Extract provider-specific metadata from response.
    
    Args:
        response: Provider response object
        provider: Provider name
        
    Returns:
        Dictionary of provider metadata
    """
    metadata = {}
    
    # Common fields to extract
    common_fields = [
        "id", "object", "created", "system_fingerprint",
        "request_id", "trace_id", "session_id"
    ]
    
    for field in common_fields:
        if hasattr(response, field):
            value = getattr(response, field)
            if value is not None:
                metadata[field] = value
    
    # Provider-specific extractions
    if provider == "openai":
        # Extract any x-request-id from headers if available
        if hasattr(response, "_headers"):
            request_id = response._headers.get("x-request-id")
            if request_id:
                metadata["x_request_id"] = request_id
    
    return metadata


def validate_tools_compatibility(
    tools: Optional[List[Tool]],
    capabilities: ProviderCapabilities
) -> List[str]:
    """Validate tool definitions for compatibility.
    
    Args:
        tools: List of tool definitions
        capabilities: Model capabilities
        
    Returns:
        List of validation warnings (empty if all valid)
    """
    warnings = []
    
    if not tools:
        return warnings
    
    if not capabilities.supports_tools:
        warnings.append(f"Model does not support tools, {len(tools)} tools will be ignored")
        return warnings
    
    for tool in tools:
        # Check for required fields
        if not tool.name:
            warnings.append("Tool missing required 'name' field")
        if not tool.description:
            warnings.append(f"Tool '{tool.name}' missing required 'description' field")
        
        # Validate parameters schema
        if tool.parameters:
            try:
                # Basic JSON schema validation
                if not isinstance(tool.parameters, dict):
                    warnings.append(f"Tool '{tool.name}' parameters must be a dictionary")
                elif "type" not in tool.parameters:
                    warnings.append(f"Tool '{tool.name}' parameters missing 'type' field")
            except Exception as e:
                warnings.append(f"Tool '{tool.name}' parameters validation error: {e}")
    
    return warnings


def prepare_messages_for_runtime(
    system: str,
    user_text: str,
    responses_use_instructions: bool = False
) -> List[Dict[str, str]]:
    """Prepare messages for agent runtime.
    
    Args:
        system: System prompt
        user_text: Formatted user text
        responses_use_instructions: Whether to use instructions format
        
    Returns:
        List of message dictionaries
    """
    if responses_use_instructions:
        # Minimal user input for Responses API
        return [
            {"role": "user", "content": user_text}
        ]
    else:
        # Standard format with system message
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text}
        ]