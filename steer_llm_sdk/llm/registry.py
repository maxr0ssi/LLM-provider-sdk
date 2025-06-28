from typing import Dict, Optional
import os
import time
from ..models.generation import ModelConfig, GenerationParams, ProviderType
from ..config.models import MODEL_CONFIGS as RAW_MODEL_CONFIGS, DEFAULT_MODEL, PROVIDER_HYPERPARAMETERS, DEFAULT_MODEL_HYPERPARAMETERS


# Convert raw configs to Pydantic models
MODEL_CONFIGS: Dict[str, ModelConfig] = {
    k: ModelConfig(**v) for k, v in RAW_MODEL_CONFIGS.items()
}

# Cache for model availability status
_model_status_cache = {}
_cache_ttl = 600  # 10 minutes cache


def get_config(llm_model_id: str) -> ModelConfig:
    """Get configuration for a specific model."""
    return MODEL_CONFIGS.get(llm_model_id, MODEL_CONFIGS[DEFAULT_MODEL])


def get_available_models() -> Dict[str, ModelConfig]:
    """Get all available models that are enabled."""
    return {k: v for k, v in MODEL_CONFIGS.items() if v.enabled}


def is_model_available(llm_model_id: str) -> bool:
    """Check if a model is available and enabled."""
    config = MODEL_CONFIGS.get(llm_model_id)
    return config is not None and config.enabled


def check_lightweight_availability(llm_model_id: str) -> bool:
    """Lightweight availability check without loading models."""
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
    normalized = {
        "model": config.llm_model_id,
        "max_tokens": min(
            raw_params.get("max_tokens", raw_params.get("maxTokens", 512)), 
            config.max_tokens
        ),
        "temperature": raw_params.get("temperature", config.temperature),
        "top_p": raw_params.get("top_p", raw_params.get("topP", 1.0)),
        "frequency_penalty": raw_params.get("frequency_penalty", raw_params.get("frequencyPenalty", 0.0)),
        "presence_penalty": raw_params.get("presence_penalty", raw_params.get("presencePenalty", 0.0)),
        "stop": raw_params.get("stop", None)
    }
    
    return GenerationParams(**normalized)


def calculate_cost(usage: Dict[str, int], config: ModelConfig) -> Optional[float]:
    """Calculate cost based on usage and model configuration."""
    if not config.cost_per_1k_tokens:
        return None
    
    total_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    return (total_tokens / 1000) * config.cost_per_1k_tokens


def get_default_hyperparameters(provider: str = None) -> dict:
    """Get default hyperparameters for a specific provider."""
    if provider and provider in PROVIDER_HYPERPARAMETERS:
        return PROVIDER_HYPERPARAMETERS[provider].copy()
    return DEFAULT_MODEL_HYPERPARAMETERS.copy()