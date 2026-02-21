"""
Provider Adapters Layer

This layer contains all LLM provider-specific implementations.
Each provider adapter translates between the SDK's normalized interface
and the provider's specific API requirements.
"""

from .base import ProviderAdapter, ProviderError

__all__ = ["ProviderAdapter", "ProviderError"]

try:
    from .openai.adapter import OpenAIProvider
    __all__.append("OpenAIProvider")
except ImportError:
    pass

try:
    from .anthropic.adapter import AnthropicProvider
    __all__.append("AnthropicProvider")
except ImportError:
    pass

try:
    from .xai.adapter import XAIProvider
    __all__.append("XAIProvider")
except ImportError:
    pass
