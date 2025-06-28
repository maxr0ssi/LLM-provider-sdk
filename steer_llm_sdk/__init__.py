"""
Steer LLM SDK - Multi-provider LLM integration with normalization and validation.

This package provides a unified interface for multiple LLM providers including:
- OpenAI (GPT models)
- Anthropic (Claude models)
- xAI (Grok models)
- Local HuggingFace models

Features:
- Normalized API across all providers
- Streaming and non-streaming generation
- Automatic parameter validation
- Cost calculation and budget management
- Conversation support
"""

__version__ = "0.1.0"

from .llm.router import LLMRouter, llm_router
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