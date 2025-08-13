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

__version__ = "0.2.0"

from .llm.router import LLMRouter, llm_router
from .main import SteerLLMClient, generate
from .llm.registry import (
    get_config,
    get_available_models,
    is_model_available,
    check_lightweight_availability,
    normalize_params,
    calculate_cost,
    get_default_hyperparameters
)
from .models.generation import (
    ProviderType,
    GenerationParams,
    GenerationRequest,
    GenerationResponse,
    ModelConfig
)
from .models.conversation_types import ConversationMessage, TurnRole as ConversationRole

__all__ = [
    # Main client
    "SteerLLMClient",
    "generate",
    
    # Router
    "LLMRouter",
    "llm_router",
    
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