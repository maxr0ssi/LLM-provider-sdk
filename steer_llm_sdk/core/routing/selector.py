from typing import Dict, Optional
import os
import time
from ...models.generation import ModelConfig, GenerationParams, ProviderType
from ...config.models import MODEL_CONFIGS as RAW_MODEL_CONFIGS, DEFAULT_MODEL, PROVIDER_HYPERPARAMETERS, DEFAULT_MODEL_HYPERPARAMETERS
from ..capabilities.models import ProviderCapabilities, get_model_capabilities


# Convert raw configs to Pydantic models
MODEL_CONFIGS: Dict[str, ModelConfig] = {
    k: ModelConfig(**v) for k, v in RAW_MODEL_CONFIGS.items()
}

# Cache for model availability status
_model_status_cache = {}
_cache_ttl = 600  # 10 minutes cache


def get_config(llm_model_id: str) -> ModelConfig:
    """Get configuration for a specific model.
    
    Handles both model IDs (e.g., 'gpt-4o-mini') and display names (e.g., 'GPT-4o Mini').
    """
    # First try direct lookup
    if llm_model_id in MODEL_CONFIGS:
        return MODEL_CONFIGS[llm_model_id]
    
    # Try to find by display name
    for model_id, config in MODEL_CONFIGS.items():
        if config.display_name == llm_model_id or config.name == llm_model_id:
            return config
    
    # Fallback to default
    return MODEL_CONFIGS[DEFAULT_MODEL]


def get_available_models() -> Dict[str, ModelConfig]:
    """Get all available models that are enabled."""
    return {k: v for k, v in MODEL_CONFIGS.items() if v.enabled}


def is_model_available(llm_model_id: str) -> bool:
    """Check if a model is available and enabled."""
    config = MODEL_CONFIGS.get(llm_model_id)
    return config is not None and config.enabled


def check_lightweight_availability(llm_model_id: str) -> bool:
    """Lightweight availability check without loading models."""
    # Allow tests to bypass availability checks
    if os.getenv('STEER_SDK_BYPASS_AVAILABILITY_CHECK') == 'true':
        return True
        
    config = get_config(llm_model_id)
    if not config.enabled:
        return False
    
    # Check cache first
    cache_key = f"{llm_model_id}_status"
    current_time = time.time()
    if cache_key in _model_status_cache:
        cached_time, cached_status = _model_status_cache[cache_key]
        if current_time - cached_time < _cache_ttl:
            return cached_status
    
    # Perform lightweight checks
    available = True
    try:
        if config.provider == ProviderType.OPENAI:
            available = bool(os.getenv('OPENAI_API_KEY'))
        elif config.provider == ProviderType.ANTHROPIC:
            available = bool(os.getenv('ANTHROPIC_API_KEY'))
        elif config.provider == ProviderType.XAI:
            available = bool(os.getenv('XAI_API_KEY'))
        else:
            available = False
    except Exception:
        available = False
    
    # Cache the result
    _model_status_cache[cache_key] = (current_time, available)
    return available


def normalize_params(raw_params: Dict, config: ModelConfig) -> GenerationParams:
    """Normalize frontend parameters to GenerationParams."""
    # Handle different parameter naming conventions
    # Ensure numeric and bounded max_tokens
    raw_max = raw_params.get("max_tokens", raw_params.get("maxTokens", 512))
    try:
        raw_max_int = int(raw_max)
    except Exception:
        raw_max_int = 512
    max_tokens_value = min(max(raw_max_int, 1), config.max_tokens)
    
    normalized = {
        "model": config.llm_model_id,
        "max_tokens": max_tokens_value,  # Always set for GenerationParams validation
        "temperature": raw_params.get("temperature", config.temperature),
        "top_p": raw_params.get("top_p", raw_params.get("topP", 1.0)),
        "frequency_penalty": raw_params.get("frequency_penalty", raw_params.get("frequencyPenalty", 0.0)),
        "presence_penalty": raw_params.get("presence_penalty", raw_params.get("presencePenalty", 0.0)),
        "stop": raw_params.get("stop", None)
    }
    
    # Pass through any additional parameters (like response_format, seed, etc.)
    # BUT exclude max_tokens from raw_params to avoid duplicates
    for key, value in raw_params.items():
        if key not in normalized and key not in ["max_tokens", "maxTokens", "topP", "frequencyPenalty", "presencePenalty"]:
            normalized[key] = value
    
    return GenerationParams(**normalized)


def get_capabilities(llm_model_id: str) -> ProviderCapabilities:
    """Get capabilities for a specific model.

    Args:
        llm_model_id: Model ID to get capabilities for

    Returns:
        ProviderCapabilities object
    """
    # Accept either exact model id or display-only variants; map to base id
    config = get_config(llm_model_id)
    base_id = config.llm_model_id
    # Normalize versioned IDs like gpt-4.1-mini-2025-04-14 → gpt-4.1-mini
    if base_id.startswith("gpt-4.1-mini"):
        base_id = "gpt-4.1-mini"
    elif base_id.startswith("o4-mini"):
        base_id = "o4-mini"
    elif base_id.startswith("gpt-5-mini"):
        base_id = "gpt-5-mini"
    elif base_id.startswith("gpt-5-nano"):
        base_id = "gpt-5-nano"
    elif base_id.startswith("gpt-5"):
        base_id = "gpt-5"
    return get_model_capabilities(base_id)


def calculate_cost(usage: Dict[str, int], config: ModelConfig) -> Optional[float]:
    """Calculate cost based on usage and model configuration using exact or blended pricing."""
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    
    if config.input_cost_per_1k_tokens and config.output_cost_per_1k_tokens:
        input_cost = (prompt_tokens / 1000) * config.input_cost_per_1k_tokens
        output_cost = (completion_tokens / 1000) * config.output_cost_per_1k_tokens
        return input_cost + output_cost
    
    # Fallback: blended single-rate pricing if available (legacy tests)
    if hasattr(config, 'cost_per_1k_tokens') and getattr(config, 'cost_per_1k_tokens'):
        total = usage.get("total_tokens", prompt_tokens + completion_tokens)
        return (total / 1000) * getattr(config, 'cost_per_1k_tokens')
    
    return None


def calculate_exact_cost(usage: Dict[str, int], model_id: str) -> Optional[float]:
    """Calculate exact cost using separate input/output token pricing."""
    config = get_config(model_id)
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    
    # Use model config pricing if available
    if config.input_cost_per_1k_tokens and config.output_cost_per_1k_tokens:
        input_cost = (prompt_tokens / 1000) * config.input_cost_per_1k_tokens
        output_cost = (completion_tokens / 1000) * config.output_cost_per_1k_tokens
        return input_cost + output_cost
    
    # Fall back to hardcoded values for legacy support
    from ...config.constants import (
        GPT4O_MINI_INPUT_COST_PER_1K,
        GPT4O_MINI_OUTPUT_COST_PER_1K,
        GPT41_NANO_INPUT_COST_PER_1K,
        GPT41_NANO_OUTPUT_COST_PER_1K,
        O4_MINI_INPUT_COST_PER_1K,
        O4_MINI_OUTPUT_COST_PER_1K,
        GPT41_MINI_INPUT_COST_PER_1K,
        GPT41_MINI_OUTPUT_COST_PER_1K
    )
    
    if model_id == "gpt-4o-mini":
        input_cost = (prompt_tokens / 1000) * GPT4O_MINI_INPUT_COST_PER_1K
        output_cost = (completion_tokens / 1000) * GPT4O_MINI_OUTPUT_COST_PER_1K
        return input_cost + output_cost
    
    elif model_id == "gpt-4.1-nano":
        input_cost = (prompt_tokens / 1000) * GPT41_NANO_INPUT_COST_PER_1K
        output_cost = (completion_tokens / 1000) * GPT41_NANO_OUTPUT_COST_PER_1K
        return input_cost + output_cost
    
    elif model_id == "o4-mini":
        input_cost = (prompt_tokens / 1000) * O4_MINI_INPUT_COST_PER_1K
        output_cost = (completion_tokens / 1000) * O4_MINI_OUTPUT_COST_PER_1K
        return input_cost + output_cost
    
    elif model_id == "gpt-4.1-mini":
        input_cost = (prompt_tokens / 1000) * GPT41_MINI_INPUT_COST_PER_1K
        output_cost = (completion_tokens / 1000) * GPT41_MINI_OUTPUT_COST_PER_1K
        return input_cost + output_cost
    
    # For other models, fall back to blended default model pricing (gpt-4o-mini)
    from ...config.constants import (
        GPT4O_MINI_INPUT_COST_PER_1K,
        GPT4O_MINI_OUTPUT_COST_PER_1K,
    )
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
    blended_rate_per_1k = (GPT4O_MINI_INPUT_COST_PER_1K + GPT4O_MINI_OUTPUT_COST_PER_1K) / 2.0
    return (total_tokens / 1000) * blended_rate_per_1k


def calculate_cache_savings(usage: Dict[str, int], model_id: str) -> float:
    """Calculate exact cost savings from cache usage."""
    from ...config.constants import (
        GPT4O_MINI_INPUT_COST_PER_1K,
        GPT41_NANO_INPUT_COST_PER_1K,
        O4_MINI_INPUT_COST_PER_1K,
        O4_MINI_CACHED_INPUT_COST_PER_1K,
        GPT41_MINI_INPUT_COST_PER_1K,
        GPT41_MINI_CACHED_INPUT_COST_PER_1K
    )
    
    cache_info = usage.get("cache_info", {})
    
    # OpenAI cache savings (cached tokens are input tokens)
    if "cached_tokens" in cache_info:
        cached_tokens = cache_info["cached_tokens"]
        if model_id == "gpt-4o-mini":
            return (cached_tokens / 1000) * GPT4O_MINI_INPUT_COST_PER_1K
        elif model_id == "gpt-4.1-nano":
            return (cached_tokens / 1000) * GPT41_NANO_INPUT_COST_PER_1K
        elif model_id == "o4-mini":
            # For o4-mini, calculate the difference between regular and cached pricing
            regular_cost = (cached_tokens / 1000) * O4_MINI_INPUT_COST_PER_1K
            cached_cost = (cached_tokens / 1000) * O4_MINI_CACHED_INPUT_COST_PER_1K
            return regular_cost - cached_cost
        elif model_id == "gpt-4.1-mini":
            # For gpt-4.1-mini, calculate the difference between regular and cached pricing
            regular_cost = (cached_tokens / 1000) * GPT41_MINI_INPUT_COST_PER_1K
            cached_cost = (cached_tokens / 1000) * GPT41_MINI_CACHED_INPUT_COST_PER_1K
            return regular_cost - cached_cost
    
    # Anthropic cache savings
    if "cache_read_tokens" in cache_info:
        cache_read_tokens = cache_info["cache_read_tokens"]
        # Anthropic Haiku input cost is ~$0.0025 per 1K tokens (combined)
        # Actual input cost is lower, estimate at $0.0005 per 1K
        return (cache_read_tokens / 1000) * 0.0005
    
    return 0.0


def get_default_hyperparameters(provider: str = None) -> dict:
    """Get default hyperparameters for a specific provider."""
    if provider and provider in PROVIDER_HYPERPARAMETERS:
        return PROVIDER_HYPERPARAMETERS[provider].copy()
    return DEFAULT_MODEL_HYPERPARAMETERS.copy()