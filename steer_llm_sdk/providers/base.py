"""
Base Provider Adapter Interface

This module defines the abstract base class for all LLM provider adapters.
All provider implementations must inherit from this class and implement
the required methods to ensure consistent behavior across providers.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional, Tuple, Union

from ..models.conversation_types import ConversationMessage
from ..models.generation import GenerationParams, GenerationResponse


class ProviderAdapter(ABC):
    """
    Abstract base class for LLM provider adapters.
    
    This class defines the standard interface that all provider adapters must implement.
    It ensures consistent behavior across different LLM providers while allowing
    provider-specific implementations.
    
    The adapter is responsible for:
    - Translating SDK parameters to provider-specific parameters
    - Making API calls to the provider
    - Normalizing responses to SDK format
    - Handling provider-specific errors
    
    Provider adapters should NOT contain:
    - Business logic
    - Cross-provider logic
    - Direct model name checks (use capabilities instead)
    """
    
    @abstractmethod
    async def generate(
        self,
        messages: Union[str, List[ConversationMessage]],
        params: GenerationParams
    ) -> GenerationResponse:
        """
        Generate a completion from the provider.
        
        This method handles non-streaming generation requests. It should:
        1. Transform messages to provider format
        2. Map parameters using capability-driven logic
        3. Make the API call
        4. Normalize the response to GenerationResponse format
        5. Ensure usage dict has standard shape
        
        Args:
            messages: Either a string prompt or list of conversation messages
            params: Generation parameters including model, temperature, etc.
            
        Returns:
            GenerationResponse with normalized fields:
            - text: The generated text
            - usage: Dict with prompt_tokens, completion_tokens, total_tokens, cache_info
            - model: The model used
            - provider: The provider name
            - finish_reason: Why generation stopped (optional)
            
        Raises:
            ProviderError: For provider-specific errors (transport, API errors)
            SchemaError: For schema validation failures (if applicable)
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: Union[str, List[ConversationMessage]],
        params: GenerationParams
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming completion from the provider.
        
        This method handles streaming generation without usage data.
        It yields text chunks as they arrive from the provider.
        
        Args:
            messages: Either a string prompt or list of conversation messages
            params: Generation parameters including model, temperature, etc.
            
        Yields:
            str: Text chunks as they arrive from the provider
            
        Raises:
            ProviderError: For provider-specific errors
        """
        pass
    
    @abstractmethod
    async def generate_stream_with_usage(
        self,
        messages: Union[str, List[ConversationMessage]],
        params: GenerationParams
    ) -> AsyncGenerator[Tuple[Optional[str], Optional[Dict]], None]:
        """
        Generate a streaming completion with usage data.
        
        This method handles streaming generation with usage tracking.
        It yields tuples of (text_chunk, usage_data) where:
        - During streaming: (text, None)
        - At completion: (None, usage_dict)
        
        The usage dict MUST have the standard shape:
        {
            "prompt_tokens": int,
            "completion_tokens": int,
            "total_tokens": int,
            "cache_info": dict  # Optional, default {}
        }
        
        Args:
            messages: Either a string prompt or list of conversation messages
            params: Generation parameters including model, temperature, etc.
            
        Yields:
            Tuple[Optional[str], Optional[Dict]]: 
            - (text_chunk, None) during streaming
            - (None, usage_dict) at completion
            
        Raises:
            ProviderError: For provider-specific errors
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available and configured.
        
        This typically checks if API keys are present and valid.
        
        Returns:
            bool: True if provider is available, False otherwise
        """
        pass
    
    def get_provider_name(self) -> str:
        """
        Get the name of this provider.
        
        By default, returns the class name without 'Provider' suffix.
        Override this method to provide a custom name.
        
        Returns:
            str: The provider name (e.g., "openai", "anthropic")
        """
        class_name = self.__class__.__name__
        if class_name.endswith("Provider"):
            return class_name[:-8].lower()
        return class_name.lower()


class ProviderError(Exception):
    """
    Base exception for provider-related errors.
    
    This should be raised for:
    - API transport errors
    - Authentication failures
    - Rate limiting
    - Transient failures that may be retryable
    
    Attributes:
        message: Error message
        provider: Provider name
        status_code: HTTP status code if applicable
        retry_after: Seconds to wait before retry if applicable
        is_retryable: Whether this error should be retried
        original_error: The original exception if wrapped
    """
    
    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retry_after = retry_after
        self.is_retryable = False  # Default, should be set by error mapper
        self.original_error = None  # Will be set by error mapper if wrapping