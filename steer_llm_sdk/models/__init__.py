"""Data models for LLM SDK."""

from .generation import (
    ProviderType,
    GenerationParams,
    GenerationRequest,
    GenerationResponse,
    ModelConfig
)
from .conversation_types import ConversationMessage, TurnRole as ConversationRole

__all__ = [
    # Generation models
    "ProviderType",
    "GenerationParams",
    "GenerationRequest",
    "GenerationResponse", 
    "ModelConfig",
    
    # Conversation models
    "ConversationMessage",
    "ConversationRole"
]