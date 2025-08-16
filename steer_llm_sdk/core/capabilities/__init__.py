"""Capability registry and policy layer.

This layer handles:
- Model capability definitions and lookup
- Capability-driven behavior policies
- Determinism and budget policies
- Feature availability detection
"""

from .loader import get_capabilities_for_model
from .models import ProviderCapabilities, get_model_capabilities, DEFAULT_CAPABILITIES, MODEL_CAPABILITIES
from .policy import (
    map_max_tokens_field,
    apply_temperature_policy,
    format_responses_api_schema,
    should_use_responses_api,
    get_deterministic_settings,
    supports_prompt_caching,
    get_cache_control_config
)

__all__ = [
    "get_capabilities_for_model", 
    "get_model_capabilities",
    "ProviderCapabilities",
    "DEFAULT_CAPABILITIES",
    "MODEL_CAPABILITIES",
    # Policy helpers
    "map_max_tokens_field",
    "apply_temperature_policy",
    "format_responses_api_schema",
    "should_use_responses_api",
    "get_deterministic_settings",
    "supports_prompt_caching",
    "get_cache_control_config"
]