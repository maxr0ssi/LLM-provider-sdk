"""
Usage aggregation for streaming responses.

This module provides token counting and usage estimation for providers
that don't include usage data in their streaming responses.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
import logging

from ..models.conversation_types import ConversationMessage

logger = logging.getLogger(__name__)

# Try to import tiktoken, but make it optional
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None
    TIKTOKEN_AVAILABLE = False
    logger.debug("tiktoken not available, will use character-based estimation")


class UsageAggregator(ABC):
    """Base class for aggregating usage data during streaming."""
    
    def __init__(self, model: str, provider: str):
        self.model = model
        self.provider = provider
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_chars = 0
        self.completion_text = ""
        
    @abstractmethod
    def estimate_prompt_tokens(self, messages: Union[str, List[ConversationMessage]]) -> int:
        """Estimate tokens in the prompt/messages."""
        pass
        
    @abstractmethod
    def add_completion_chunk(self, text: str) -> None:
        """Add a chunk of completion text for token counting."""
        pass
        
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        pass
        
    @abstractmethod
    def get_confidence(self) -> float:
        """Get confidence score for the estimation (0.0-1.0)."""
        pass
        
    def get_usage(self) -> Dict[str, Any]:
        """Get the aggregated usage data."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "confidence": self.get_confidence(),
            "method": self.__class__.__name__
        }
        
    def _messages_to_text(self, messages: Union[str, List[ConversationMessage]]) -> str:
        """Convert messages to text for token counting."""
        if isinstance(messages, str):
            return messages
            
        # Convert conversation messages to text
        text_parts = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
                text_parts.append(f"{role}: {content}")
            elif hasattr(msg, "role") and hasattr(msg, "content"):
                text_parts.append(f"{msg.role}: {msg.content}")
            else:
                text_parts.append(str(msg))
                
        return "\n".join(text_parts)


class TiktokenAggregator(UsageAggregator):
    """Token counting using tiktoken for accurate OpenAI model counts."""
    
    # Model to encoding mapping
    MODEL_ENCODINGS = {
        "gpt-4": "cl100k_base",
        "gpt-4o": "cl100k_base",  # o200k_base may not be available yet
        "gpt-4o-mini": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "gpt-3.5": "cl100k_base",
        "text-davinci": "p50k_base",
        "davinci": "p50k_base",
        "o1": "cl100k_base",
        "o1-mini": "cl100k_base",
        "o1-preview": "cl100k_base",
    }
    
    def __init__(self, model: str, provider: str):
        super().__init__(model, provider)
        if not TIKTOKEN_AVAILABLE:
            raise ImportError("tiktoken is required for TiktokenAggregator. Install with: pip install tiktoken")
            
        self.encoding = self._get_encoding(model)
        
    def _get_encoding(self, model: str):
        """Get the appropriate encoding for the model."""
        # Try exact match first
        model_lower = model.lower()
        
        # Check for exact match in mapping
        for model_prefix, encoding_name in self.MODEL_ENCODINGS.items():
            if model_prefix in model_lower:
                return tiktoken.get_encoding(encoding_name)
                
        # Default to cl100k_base for unknown OpenAI models
        if self.provider == "openai":
            logger.debug(f"Unknown OpenAI model {model}, using cl100k_base encoding")
            return tiktoken.get_encoding("cl100k_base")
            
        # For non-OpenAI, try to get encoding by model name
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            # Final fallback
            logger.debug(f"No encoding found for {model}, using cl100k_base")
            return tiktoken.get_encoding("cl100k_base")
            
    def estimate_prompt_tokens(self, messages: Union[str, List[ConversationMessage]]) -> int:
        """Estimate tokens in the prompt using tiktoken."""
        text = self._messages_to_text(messages)
        self.prompt_tokens = self.count_tokens(text)
        
        # Add overhead for message formatting (roughly 4 tokens per message)
        if isinstance(messages, list):
            self.prompt_tokens += len(messages) * 4
            
        return self.prompt_tokens
        
    def add_completion_chunk(self, text: str) -> None:
        """Add completion chunk and update token count."""
        if text:
            self.completion_text += text
            # Recount tokens (more accurate than incremental)
            self.completion_tokens = self.count_tokens(self.completion_text)
            
    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        if not text:
            return 0
        return len(self.encoding.encode(text))
        
    def get_confidence(self) -> float:
        """High confidence for tiktoken-based counting."""
        return 0.95  # Very accurate for OpenAI models


class CharacterAggregator(UsageAggregator):
    """Fallback character-based token estimation."""
    
    # Provider-specific character-to-token ratios
    PROVIDER_RATIOS = {
        "openai": 4.0,      # GPT models average ~4 chars/token
        "anthropic": 3.5,   # Claude models average ~3.5 chars/token  
        "xai": 4.2,         # xAI models average ~4.2 chars/token
        "default": 4.0      # Default ratio
    }
    
    def __init__(self, model: str, provider: str):
        super().__init__(model, provider)
        self.chars_per_token = self.PROVIDER_RATIOS.get(provider, self.PROVIDER_RATIOS["default"])
        
    def estimate_prompt_tokens(self, messages: Union[str, List[ConversationMessage]]) -> int:
        """Estimate tokens based on character count."""
        text = self._messages_to_text(messages)
        self.total_chars = len(text)
        self.prompt_tokens = self.count_tokens(text)
        
        # Add overhead for message formatting
        if isinstance(messages, list):
            self.prompt_tokens += len(messages) * 4
            
        return self.prompt_tokens
        
    def add_completion_chunk(self, text: str) -> None:
        """Add completion chunk and update token estimate."""
        if text:
            self.completion_text += text
            self.completion_tokens = self.count_tokens(self.completion_text)
            
    def count_tokens(self, text: str) -> int:
        """Estimate tokens based on character count."""
        if not text:
            return 0
        # Round up to avoid underestimation
        return int((len(text) / self.chars_per_token) + 0.5)
        
    def get_confidence(self) -> float:
        """Lower confidence for character-based estimation."""
        # Confidence varies by provider accuracy
        provider_confidence = {
            "openai": 0.75,     # Well-studied ratio
            "anthropic": 0.70,  # Less data available
            "xai": 0.65,        # Newer, less studied
            "default": 0.60
        }
        return provider_confidence.get(self.provider, provider_confidence["default"])


def create_usage_aggregator(
    model: str, 
    provider: str,
    prefer_tiktoken: bool = True
) -> UsageAggregator:
    """
    Factory function to create appropriate usage aggregator.
    
    Args:
        model: Model name
        provider: Provider name
        prefer_tiktoken: Whether to prefer tiktoken if available
        
    Returns:
        UsageAggregator instance
    """
    # Use tiktoken for OpenAI models if available and preferred
    if prefer_tiktoken and TIKTOKEN_AVAILABLE and provider == "openai":
        try:
            return TiktokenAggregator(model, provider)
        except Exception as e:
            logger.debug(f"Failed to create TiktokenAggregator: {e}, falling back to character-based")
            
    # Fallback to character-based aggregator
    return CharacterAggregator(model, provider)