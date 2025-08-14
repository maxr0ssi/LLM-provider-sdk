"""Routing layer for provider selection and request routing.

This layer handles:
- Provider selection based on model and capabilities
- Request routing to appropriate providers
- Load balancing and failover logic
- Provider availability checks
"""

from .router import LLMRouter, router
from .selector import (
    get_config,
    get_available_models,
    is_model_available,
    check_lightweight_availability,
    normalize_params,
    get_capabilities,
    calculate_cost,
    calculate_exact_cost,
    calculate_cache_savings,
    get_default_hyperparameters,
    MODEL_CONFIGS
)

__all__ = [
    "LLMRouter",
    "router",
    "get_config",
    "get_available_models", 
    "is_model_available",
    "check_lightweight_availability",
    "normalize_params",
    "get_capabilities",
    "calculate_cost",
    "calculate_exact_cost",
    "calculate_cache_savings",
    "get_default_hyperparameters",
    "MODEL_CONFIGS"
]