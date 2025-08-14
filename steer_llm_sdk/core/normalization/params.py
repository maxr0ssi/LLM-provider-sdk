"""
Parameter normalization module.

This module provides functions to normalize parameters based on model capabilities.
It ensures consistent parameter handling across different providers and models
without hardcoded model name checks.
"""

from typing import Any, Dict, Optional

from ..capabilities.models import ProviderCapabilities, get_model_capabilities
from ..capabilities.policy import (
    map_max_tokens_field,
    apply_temperature_policy,
    should_use_responses_api as policy_should_use_responses_api
)
from ...models.generation import GenerationParams


def normalize_params(
    params: GenerationParams,
    model_id: str,
    provider: str,
    capabilities: Optional[ProviderCapabilities] = None
) -> Dict[str, Any]:
    """
    Normalize parameters based on model capabilities.
    
    This function transforms SDK parameters into provider-specific parameters
    based on the model's capabilities. It handles:
    - max_tokens vs max_output_tokens vs max_completion_tokens
    - temperature handling (omit if unsupported, clamp if fixed)
    - seed propagation only when supported
    - response format based on capabilities
    - provider-specific parameter names
    
    Args:
        params: SDK generation parameters
        model_id: The model identifier
        provider: The provider name
        capabilities: Optional pre-fetched capabilities (will fetch if not provided)
        
    Returns:
        Dict with normalized parameters ready for provider API
    """
    # Get capabilities if not provided
    if capabilities is None:
        capabilities = get_model_capabilities(model_id)
    
    # Start with base parameters
    normalized = {
        "model": params.model,
    }
    
    # Handle max tokens based on capabilities
    if params.max_tokens is not None:
        # Use policy helper to determine correct field name
        use_responses_api = policy_should_use_responses_api(
            {"response_format": getattr(params, "response_format", None)},
            capabilities
        )
        field_name = map_max_tokens_field(capabilities, provider, use_responses_api)
        normalized[field_name] = params.max_tokens
    
    # Handle temperature based on capabilities
    if hasattr(params, "temperature") and params.temperature is not None:
        # Add temperature to params dict for policy application
        temp_params = {"temperature": params.temperature}
        # Apply temperature policy
        temp_params = apply_temperature_policy(temp_params, capabilities)
        # Copy temperature to normalized if it wasn't removed
        if "temperature" in temp_params:
            normalized["temperature"] = temp_params["temperature"]
    elif capabilities.requires_temperature_one:
        # Even if no temperature provided, some models require it
        normalized["temperature"] = 1.0
    
    # Handle top_p
    if hasattr(params, "top_p") and params.top_p is not None:
        normalized["top_p"] = params.top_p
    
    # Handle seed (only when supported)
    if hasattr(params, "seed") and params.seed is not None and capabilities.supports_seed:
        normalized["seed"] = params.seed
    
    # Handle stop sequences
    if hasattr(params, "stop") and params.stop is not None:
        if provider == "anthropic":
            normalized["stop_sequences"] = params.stop
        else:
            normalized["stop"] = params.stop
    
    # Handle response format (for structured output)
    if hasattr(params, "response_format") and params.response_format is not None:
        if capabilities.supports_response_format:
            normalized["response_format"] = params.response_format
    
    # Provider-specific parameters
    if provider == "openai":
        # OpenAI-specific
        if hasattr(params, "frequency_penalty") and params.frequency_penalty is not None:
            normalized["frequency_penalty"] = params.frequency_penalty
        if hasattr(params, "presence_penalty") and params.presence_penalty is not None:
            normalized["presence_penalty"] = params.presence_penalty
        if hasattr(params, "logprobs") and params.logprobs is not None and capabilities.supports_logprobs:
            normalized["logprobs"] = params.logprobs
            
    elif provider == "anthropic":
        # Anthropic-specific
        if hasattr(params, "top_k") and params.top_k is not None:
            normalized["top_k"] = params.top_k
            
    # Handle metadata fields (for Responses API)
    if hasattr(params, "metadata") and params.metadata is not None:
        # Extract Responses API specific fields
        metadata = params.metadata
        if isinstance(metadata, dict):
            if metadata.get("strict") is not None:
                normalized["strict"] = metadata["strict"]
            if metadata.get("responses_use_instructions") is not None:
                normalized["responses_use_instructions"] = metadata["responses_use_instructions"]
            if metadata.get("reasoning") is not None:
                normalized["reasoning"] = metadata["reasoning"]
    
    return normalized


def should_use_responses_api(
    params: GenerationParams,
    model_id: str,
    capabilities: Optional[ProviderCapabilities] = None
) -> bool:
    """
    Determine if OpenAI Responses API should be used.
    
    Args:
        params: Generation parameters
        model_id: The model identifier
        capabilities: Optional pre-fetched capabilities
        
    Returns:
        bool: True if Responses API should be used
    """
    if capabilities is None:
        capabilities = get_model_capabilities(model_id)
    
    # Use Responses API if:
    # 1. Model supports JSON schema AND
    # 2. Response format with schema is requested
    if (capabilities.supports_json_schema and 
        hasattr(params, "response_format") and 
        params.response_format is not None):
        rf = params.response_format
        if isinstance(rf, dict):
            # Check for json_schema or schema field
            if "json_schema" in rf or "schema" in rf:
                return True
    
    return False


def transform_messages_for_provider(
    messages: list,
    provider: str,
    use_instructions: bool = False
) -> Any:
    """
    Transform messages into provider-specific format.
    
    Args:
        messages: List of messages in SDK format
        provider: Provider name
        use_instructions: Whether to use instructions field (Responses API)
        
    Returns:
        Transformed messages in provider format
    """
    if provider == "openai":
        if use_instructions and messages and messages[0].get("role") == "system":
            # For Responses API with instructions mapping
            return {
                "instructions": messages[0]["content"],
                "input": messages[1:]  # Responses API uses "input", not "messages"
            }
        else:
            # Standard format
            return messages
            
    elif provider == "anthropic":
        # Anthropic expects system message separately
        system_message = None
        user_messages = []
        
        for msg in messages:
            if msg.get("role") == "system":
                if system_message is None:
                    system_message = msg["content"]
                else:
                    # Multiple system messages - concatenate
                    system_message += "\n\n" + msg["content"]
            else:
                user_messages.append(msg)
        
        return {
            "system": system_message,
            "messages": user_messages
        }
        
    else:
        # Default: return as-is
        return messages


def apply_deterministic_policy(
    params: Dict[str, Any],
    capabilities: ProviderCapabilities,
    deterministic: bool = False
) -> Dict[str, Any]:
    """
    Apply deterministic policy to parameters.
    
    Args:
        params: Normalized parameters
        capabilities: Model capabilities
        deterministic: Whether to apply deterministic settings
        
    Returns:
        Parameters with deterministic policy applied
    """
    if not deterministic:
        return params
    
    # Apply deterministic settings
    if "temperature" in params:
        # Clamp temperature to deterministic max
        if capabilities.deterministic_temperature_max is not None:
            params["temperature"] = min(
                params.get("temperature", 0),
                capabilities.deterministic_temperature_max
            )
    
    # Set deterministic top_p
    if capabilities.deterministic_top_p is not None:
        params["top_p"] = capabilities.deterministic_top_p
    
    # Ensure seed is set if supported
    if capabilities.supports_seed and "seed" not in params:
        # Use a default seed for determinism
        params["seed"] = 42
    
    return params