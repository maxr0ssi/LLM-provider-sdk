"""
Usage normalization module.

This module provides functions to normalize usage data from different providers
into a consistent format. All providers must use these functions to ensure
consistent usage reporting across the SDK.
"""

from typing import Any, Dict, Optional


def normalize_usage(
    usage_data: Optional[Dict[str, Any]],
    provider: str,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cache_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Normalize usage data into standard SDK format.
    
    This function ensures all usage data follows the standard shape:
    {
        "prompt_tokens": int,
        "completion_tokens": int,
        "total_tokens": int,
        "cache_info": dict
    }
    
    Args:
        usage_data: Raw usage data from provider (optional)
        provider: Provider name for provider-specific handling
        prompt_tokens: Override for prompt tokens
        completion_tokens: Override for completion tokens
        total_tokens: Override for total tokens
        cache_info: Cache information if available
        
    Returns:
        Dict with normalized usage data
    """
    # Start with defaults
    normalized = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cache_info": {}
    }
    
    # If no usage data provided, use overrides if available
    if not usage_data:
        if prompt_tokens is not None:
            normalized["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            normalized["completion_tokens"] = completion_tokens
        if total_tokens is not None:
            normalized["total_tokens"] = total_tokens
        else:
            # Calculate total if not provided
            normalized["total_tokens"] = normalized["prompt_tokens"] + normalized["completion_tokens"]
        if cache_info:
            normalized["cache_info"] = cache_info
        return normalized
    
    # Provider-specific field mapping
    if provider == "openai":
        normalized["prompt_tokens"] = usage_data.get("prompt_tokens", 0)
        normalized["completion_tokens"] = usage_data.get("completion_tokens", 0)
        normalized["total_tokens"] = usage_data.get("total_tokens", 0)
        
        # Handle cache info
        cache = {}
        if "prompt_tokens_details" in usage_data:
            details = usage_data["prompt_tokens_details"]
            if isinstance(details, dict) and "cached_tokens" in details:
                cache["cached_tokens"] = details["cached_tokens"]
                cache["prompt_tokens_details"] = details
        if "cached_tokens" in usage_data:
            cache["cached_tokens"] = usage_data["cached_tokens"]
        if cache:
            normalized["cache_info"] = cache
            
    elif provider == "anthropic":
        # Anthropic uses input_tokens/output_tokens
        normalized["prompt_tokens"] = usage_data.get("input_tokens", 0)
        normalized["completion_tokens"] = usage_data.get("output_tokens", 0)
        normalized["total_tokens"] = usage_data.get("total_tokens", 0)
        
        # Handle cache info
        if "cache_creation_input_tokens" in usage_data or "cache_read_input_tokens" in usage_data:
            normalized["cache_info"] = {
                "cache_creation_input_tokens": usage_data.get("cache_creation_input_tokens", 0),
                "cache_read_input_tokens": usage_data.get("cache_read_input_tokens", 0)
            }
            
    elif provider == "xai":
        # xAI might use different field names
        normalized["prompt_tokens"] = usage_data.get("prompt_tokens", 
                                                   usage_data.get("input_tokens", 0))
        normalized["completion_tokens"] = usage_data.get("completion_tokens",
                                                       usage_data.get("output_tokens", 0))
        normalized["total_tokens"] = usage_data.get("total_tokens", 0)
        
    else:
        # Generic mapping for unknown providers
        # Try common field names
        for prompt_field in ["prompt_tokens", "input_tokens", "prompt_token_count"]:
            if prompt_field in usage_data:
                normalized["prompt_tokens"] = usage_data[prompt_field]
                break
                
        for completion_field in ["completion_tokens", "output_tokens", "generated_tokens"]:
            if completion_field in usage_data:
                normalized["completion_tokens"] = usage_data[completion_field]
                break
                
        normalized["total_tokens"] = usage_data.get("total_tokens", 0)
    
    # Apply overrides if provided
    if prompt_tokens is not None:
        normalized["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        normalized["completion_tokens"] = completion_tokens
    if total_tokens is not None:
        normalized["total_tokens"] = total_tokens
    if cache_info is not None:
        normalized["cache_info"] = cache_info
        
    # Ensure all values are integers first
    normalized["prompt_tokens"] = int(normalized["prompt_tokens"])
    normalized["completion_tokens"] = int(normalized["completion_tokens"])
    normalized["total_tokens"] = int(normalized["total_tokens"])
    
    # Ensure total_tokens is accurate (after conversion to int)
    if normalized["total_tokens"] == 0:
        normalized["total_tokens"] = normalized["prompt_tokens"] + normalized["completion_tokens"]
    
    return normalized


def extract_cache_info(usage_data: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """
    Extract cache information from provider usage data.
    
    Args:
        usage_data: Raw usage data from provider
        provider: Provider name
        
    Returns:
        Dict with cache information or empty dict
    """
    cache_info = {}
    
    if provider == "openai":
        # OpenAI cache info in prompt_tokens_details
        if "prompt_tokens_details" in usage_data:
            details = usage_data["prompt_tokens_details"]
            if isinstance(details, dict):
                cache_info["prompt_tokens_details"] = details
                if "cached_tokens" in details:
                    cache_info["cached_tokens"] = details["cached_tokens"]
        # Also check direct cached_tokens
        if "cached_tokens" in usage_data:
            cache_info["cached_tokens"] = usage_data["cached_tokens"]
            
    elif provider == "anthropic":
        # Anthropic cache info
        if "cache_creation_input_tokens" in usage_data:
            cache_info["cache_creation_input_tokens"] = usage_data["cache_creation_input_tokens"]
        if "cache_read_input_tokens" in usage_data:
            cache_info["cache_read_input_tokens"] = usage_data["cache_read_input_tokens"]
            
    # Other providers can be added here
    
    return cache_info


def calculate_usage_cost(
    usage: Dict[str, Any],
    input_cost_per_1k: float,
    output_cost_per_1k: float,
    cached_cost_per_1k: Optional[float] = None
) -> float:
    """
    Calculate the cost of usage based on token counts and pricing.
    
    Args:
        usage: Normalized usage dict
        input_cost_per_1k: Cost per 1K input tokens
        output_cost_per_1k: Cost per 1K output tokens
        cached_cost_per_1k: Cost per 1K cached tokens (optional)
        
    Returns:
        Total cost in USD
    """
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    
    # Calculate base cost
    input_cost = (prompt_tokens / 1000) * input_cost_per_1k
    output_cost = (completion_tokens / 1000) * output_cost_per_1k
    
    # Handle cached tokens if pricing available
    cache_savings = 0.0
    if cached_cost_per_1k is not None and "cache_info" in usage:
        cache_info = usage["cache_info"]
        cached_tokens = cache_info.get("cached_tokens", 0)
        if cached_tokens > 0:
            # Cached tokens are charged at cached rate instead of input rate
            normal_cached_cost = (cached_tokens / 1000) * input_cost_per_1k
            actual_cached_cost = (cached_tokens / 1000) * cached_cost_per_1k
            cache_savings = normal_cached_cost - actual_cached_cost
    
    return input_cost + output_cost - cache_savings