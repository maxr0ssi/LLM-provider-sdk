# Model family base configurations
from typing import Dict, Any

# Base configurations for model families
MODEL_FAMILIES = {
    "gpt-4": {
        "provider": "openai",
        "temperature": 0.7,
        "enabled": True,
        # Base GPT-4 pricing (can be overridden)
        "input_cost_per_1k_tokens": 0.003,
        "output_cost_per_1k_tokens": 0.006,
    },
    "gpt-4.1": {
        "provider": "openai", 
        "temperature": 0.7,
        "enabled": True,
        # Enhanced GPT-4.1 pricing
        "input_cost_per_1k_tokens": 0.002,
        "output_cost_per_1k_tokens": 0.008,
    },
    "gpt-5": {
        "provider": "openai",
        "temperature": 0.7,
        "enabled": True,
        # GPT-5 premium pricing
        "input_cost_per_1k_tokens": 0.00125,
        "output_cost_per_1k_tokens": 0.01,
    },
    "claude-3": {
        "provider": "anthropic",
        "temperature": 0.7,
        "enabled": True,
    },
    "grok": {
        "provider": "xai",
        "temperature": 0.7,
        "enabled": True,
    }
}

def create_model_config(family: str, variant: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Create a model configuration by combining family defaults with variant overrides."""
    if family not in MODEL_FAMILIES:
        raise ValueError(f"Unknown model family: {family}")
    
    base = MODEL_FAMILIES[family].copy()
    base.update(overrides)
    
    # Ensure required fields
    if "name" not in base:
        base["name"] = variant
    if "display_name" not in base:
        base["display_name"] = variant.replace("-", " ").title()
    if "llm_model_id" not in base:
        base["llm_model_id"] = variant
        
    return base