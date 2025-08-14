"""
Capability-driven policy helpers.

This module provides helper functions that make decisions based on model capabilities
rather than hardcoded model names. All policy decisions should flow through these
helpers to ensure consistent capability-driven behavior.
"""

from typing import Any, Dict, Optional

from .models import ProviderCapabilities


def map_max_tokens_field(
    capabilities: ProviderCapabilities,
    provider: str,
    use_responses_api: bool = False
) -> str:
    """
    Determine the correct max tokens field name based on capabilities.
    
    Args:
        capabilities: Model capabilities
        provider: Provider name (e.g., "openai", "anthropic")
        use_responses_api: Whether Responses API is being used
        
    Returns:
        The correct field name: 'max_tokens', 'max_completion_tokens', or 'max_output_tokens'
    """
    # For Responses API, always use max_output_tokens if supported
    if use_responses_api and capabilities.uses_max_output_tokens_in_responses_api:
        return "max_output_tokens"
    
    # For models that use max_completion_tokens (like o4-mini)
    if capabilities.uses_max_completion_tokens:
        return "max_completion_tokens"
    
    # Default to standard max_tokens
    return "max_tokens"


def apply_temperature_policy(
    params: Dict[str, Any],
    capabilities: ProviderCapabilities
) -> Dict[str, Any]:
    """
    Apply temperature rules based on model capabilities.
    
    This function:
    - Omits temperature if the model doesn't support it
    - Forces temperature to 1.0 if required by the model
    - Clamps temperature for deterministic mode
    
    Args:
        params: Parameters dict that may contain temperature
        capabilities: Model capabilities
        
    Returns:
        Updated parameters dict with temperature policy applied
    """
    # Copy params to avoid modifying the original
    result = params.copy()
    
    # Check if temperature is in params
    if "temperature" not in result:
        # If model requires temperature=1.0, add it
        if capabilities.requires_temperature_one:
            result["temperature"] = 1.0
        return result
    
    # Model doesn't support temperature - remove it
    if not capabilities.supports_temperature:
        result.pop("temperature", None)
        return result
    
    # Model requires temperature=1.0 - force it
    if capabilities.requires_temperature_one:
        result["temperature"] = 1.0
        return result
    
    # Apply deterministic temperature clamping if needed
    if capabilities.deterministic_temperature_max is not None:
        current_temp = result.get("temperature", 0.0)
        if current_temp > capabilities.deterministic_temperature_max:
            result["temperature"] = capabilities.deterministic_temperature_max
    
    return result


def format_responses_api_schema(
    schema: Dict[str, Any],
    name: str,
    strict: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Format a JSON schema for OpenAI Responses API.
    
    Ensures the schema follows Responses API requirements:
    - Uses text.format structure with type="json_schema"
    - Adds additionalProperties=false to root schema
    - Includes name and optional strict flag
    
    Args:
        schema: The JSON schema to format
        name: Name for the schema (required by Responses API)
        strict: Optional strict mode flag
        
    Returns:
        Properly formatted text.format configuration
    """
    # Ensure schema has additionalProperties=false at root
    formatted_schema = dict(schema)
    if "additionalProperties" not in formatted_schema:
        formatted_schema["additionalProperties"] = False
    
    # Build text.format structure
    text_format = {
        "type": "json_schema",
        "name": name,
        "schema": formatted_schema
    }
    
    # Add strict flag if provided
    if strict is not None:
        text_format["strict"] = strict
    
    return {"format": text_format}


def should_use_responses_api(
    params: Dict[str, Any],
    capabilities: ProviderCapabilities
) -> bool:
    """
    Determine if OpenAI Responses API should be used.
    
    The Responses API is used when:
    1. The model supports JSON schema (capabilities.supports_json_schema)
    2. A response_format with schema is requested
    
    Args:
        params: Request parameters
        capabilities: Model capabilities
        
    Returns:
        True if Responses API should be used, False otherwise
    """
    # Model must support JSON schema
    if not capabilities.supports_json_schema:
        return False
    
    # Check if response_format with schema is requested
    response_format = params.get("response_format")
    if not response_format or not isinstance(response_format, dict):
        return False
    
    # Look for json_schema or schema field
    if "json_schema" in response_format or "schema" in response_format:
        return True
    
    return False


def get_deterministic_settings(
    capabilities: ProviderCapabilities,
    deterministic: bool = False
) -> Dict[str, Any]:
    """
    Get deterministic settings for a model based on capabilities.
    
    Args:
        capabilities: Model capabilities
        deterministic: Whether to apply deterministic settings
        
    Returns:
        Dict with deterministic parameters (temperature, top_p, seed)
    """
    if not deterministic:
        return {}
    
    settings = {}
    
    # Apply deterministic temperature
    if capabilities.requires_temperature_one:
        settings["temperature"] = 1.0
    elif capabilities.deterministic_temperature_max is not None:
        settings["temperature"] = capabilities.deterministic_temperature_max
    
    # Apply deterministic top_p
    if capabilities.deterministic_top_p is not None:
        settings["top_p"] = capabilities.deterministic_top_p
    
    # Add seed if supported
    if capabilities.supports_seed:
        settings["seed"] = 42  # Default deterministic seed
    
    return settings


def supports_prompt_caching(
    capabilities: ProviderCapabilities,
    provider: str
) -> bool:
    """
    Check if prompt caching is supported and should be used.
    
    Args:
        capabilities: Model capabilities
        provider: Provider name
        
    Returns:
        True if prompt caching should be used
    """
    return capabilities.supports_prompt_caching and capabilities.cache_ttl_seconds is not None


def get_cache_control_config(
    capabilities: ProviderCapabilities,
    provider: str,
    message_length: int,
    threshold: int = 1024
) -> Optional[Dict[str, Any]]:
    """
    Get cache control configuration for long messages.
    
    Args:
        capabilities: Model capabilities
        provider: Provider name
        message_length: Length of the message to potentially cache
        threshold: Minimum length for caching (default 1024)
        
    Returns:
        Cache control config or None if caching not applicable
    """
    if not supports_prompt_caching(capabilities, provider):
        return None
    
    if message_length < threshold:
        return None
    
    # Return provider-specific cache control format
    if provider == "openai":
        return {"type": "ephemeral"}
    elif provider == "anthropic":
        return {"type": "ephemeral"}
    
    return None