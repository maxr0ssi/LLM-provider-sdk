"""
Steer LLM SDK - Multi-provider LLM integration with normalization and validation.

This package provides a unified interface for multiple LLM providers including:
- OpenAI (GPT models)
- Anthropic (Claude models)
- xAI (Grok models)

Features:
- Normalized API across all providers
- Streaming and non-streaming generation
- Automatic parameter validation
- Cost calculation and budget management
- Conversation support
"""

__version__ = "0.3.1"

from .api.client import SteerLLMClient, generate
from .core.routing import (
    LLMRouter,
    calculate_cost,
    check_lightweight_availability,
    get_available_models,
    get_config,
    get_default_hyperparameters,
    is_model_available,
    normalize_params,
)
# Router instance removed - create with SteerLLMClient instead
from .models.conversation_types import ConversationMessage
from .models.conversation_types import TurnRole as ConversationRole
from .models.generation import (
    GenerationParams,
    GenerationRequest,
    GenerationResponse,
    ModelConfig,
    ProviderType,
)

__all__ = [
    # Main client
    "SteerLLMClient",
    "generate",
    
    # Router
    "LLMRouter",
    
    # Registry functions
    "get_config",
    "get_available_models", 
    "is_model_available",
    "check_lightweight_availability",
    "normalize_params",
    "calculate_cost",
    "get_default_hyperparameters",
    
    # Models
    "ProviderType",
    "GenerationParams",
    "GenerationRequest", 
    "GenerationResponse",
    "ModelConfig",
    "ConversationMessage",
    "ConversationRole"
]