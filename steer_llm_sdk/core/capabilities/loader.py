from __future__ import annotations

from typing import Optional

from ...config.models import MODEL_CONFIGS
from .models import ProviderCapabilities, get_model_capabilities, DEFAULT_CAPABILITIES


def get_capabilities_for_model(model_identifier: str) -> ProviderCapabilities:
    """Return capabilities for a given model id.
    
    This function first tries to find the model in the comprehensive MODEL_CAPABILITIES
    registry. If not found, it tries to match by various model identifiers in the config.
    
    Args:
        model_identifier: The model ID to look up
        
    Returns:
        ProviderCapabilities for the model, or DEFAULT_CAPABILITIES if not found
    """
    # First try the direct lookup in the comprehensive registry
    caps = get_model_capabilities(model_identifier)
    if caps != DEFAULT_CAPABILITIES:
        return caps
    
    # If not found, try to find by config aliases
    config = MODEL_CONFIGS.get(model_identifier)
    if not config:
        # Fallback: search by llm_model_id or display fields
        for key, cfg in MODEL_CONFIGS.items():
            if isinstance(cfg, dict):
                if cfg.get("llm_model_id") == model_identifier or cfg.get("name") == model_identifier or cfg.get("display_name") == model_identifier:
                    # Try to find capabilities by the registry key
                    return get_model_capabilities(key)
    
    # If we found a config but no capabilities, try by the config's model ID
    if config:
        llm_model_id = config.get("llm_model_id") if isinstance(config, dict) else getattr(config, "llm_model_id", None)
        if llm_model_id:
            caps = get_model_capabilities(llm_model_id)
            if caps != DEFAULT_CAPABILITIES:
                return caps
    
    # Return default capabilities as last resort
    return DEFAULT_CAPABILITIES


