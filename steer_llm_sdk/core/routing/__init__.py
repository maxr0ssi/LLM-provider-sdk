"""Routing layer for provider selection and request routing.

This layer handles:
- Provider selection based on model and capabilities
- Request routing to appropriate providers
- Load balancing and failover logic
- Provider availability checks
"""

from .router import LLMRouter
from .selector import (
    MODEL_CONFIGS,
    calculate_cache_savings,
    calculate_cost,
    calculate_exact_cost,
    check_lightweight_availability,
    get_available_models,
    get_capabilities,
    get_config,
    get_default_hyperparameters,
    is_model_available,
    normalize_params,
)

__all__ = [
    "LLMRouter",
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