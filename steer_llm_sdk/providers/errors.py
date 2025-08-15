"""
Error mapping utilities for provider adapters.

This module provides consistent error mapping across all providers,
converting provider-specific errors to standardized ProviderError instances.
"""

from typing import Optional, Type, Dict, Any
import httpx

from .base import ProviderError
from ..reliability.error_classifier import ErrorClassifier, ErrorCategory


class ErrorMapper:
    """Maps provider-specific errors to standardized ProviderError."""
    
    # Common HTTP status codes that indicate retryable errors
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    
    @staticmethod
    def is_retryable(error: Exception) -> bool:
        """
        Determine if an error is retryable.
        
        Args:
            error: The exception to check
            
        Returns:
            bool: True if the error is retryable
        """
        # Check for HTTP status codes
        if hasattr(error, 'status_code') and error.status_code is not None:
            if error.status_code in ErrorMapper.RETRYABLE_STATUS_CODES:
                return True
        
        # Check for specific error types
        if isinstance(error, (httpx.TimeoutException, httpx.ConnectError)):
            return True
        
        # Check for rate limit errors in message
        try:
            error_msg = str(error).lower()
            if any(phrase in error_msg for phrase in ['rate limit', 'too many requests', 'quota exceeded', 'too_many_requests']):
                return True
        except Exception:
            # If str() fails, continue to check other attributes
            pass
        
        # Also check message attribute if present
        if hasattr(error, 'message'):
            msg = str(error.message).lower()
            if any(phrase in msg for phrase in ['rate limit', 'too many requests', 'quota exceeded', 'too_many_requests']):
                return True
        
        return False
    
    @staticmethod
    def get_retry_after(error: Exception) -> Optional[float]:
        """
        Extract retry-after value from error if available.
        
        Args:
            error: The exception to check
            
        Returns:
            Optional[float]: Seconds to wait before retry, or None
        """
        # Check for Retry-After header
        if hasattr(error, 'response') and hasattr(error.response, 'headers'):
            retry_after = error.response.headers.get('Retry-After')
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        
        # Check for rate limit reset time in error
        if hasattr(error, 'retry_after'):
            return error.retry_after
        
        return None
    
    @staticmethod
    def map_openai_error(error: Exception) -> ProviderError:
        """
        Map OpenAI-specific errors to ProviderError.
        
        Args:
            error: The OpenAI exception
            
        Returns:
            ProviderError with appropriate metadata
        """
        # Use ErrorClassifier for comprehensive classification
        classification = ErrorClassifier.classify_error(error, "openai")
        
        status_code = getattr(error, 'status_code', None)
        retry_after = classification.suggested_delay or ErrorMapper.get_retry_after(error)
        
        # Use classified user message or fallback
        if classification.user_message:
            message = f"OpenAI API error: {classification.user_message}"
        elif hasattr(error, 'message'):
            message = f"OpenAI API error: {error.message}"
        else:
            message = f"OpenAI API error: {str(error)}"
        
        # Create ProviderError with metadata
        provider_error = ProviderError(
            message=message,
            provider="openai",
            status_code=status_code,
            retry_after=retry_after
        )
        
        # Use classification for retryable flag
        provider_error.is_retryable = classification.is_retryable
        
        # Add original error reference
        provider_error.original_error = error
        
        # Add error category as an attribute
        provider_error.error_category = classification.category
        
        return provider_error
    
    @staticmethod
    def map_anthropic_error(error: Exception) -> ProviderError:
        """
        Map Anthropic-specific errors to ProviderError.
        
        Args:
            error: The Anthropic exception
            
        Returns:
            ProviderError with appropriate metadata
        """
        # Use ErrorClassifier for comprehensive classification
        classification = ErrorClassifier.classify_error(error, "anthropic")
        
        status_code = getattr(error, 'status_code', None)
        retry_after = classification.suggested_delay or ErrorMapper.get_retry_after(error)
        
        # Use classified user message or fallback
        if classification.user_message:
            message = f"Anthropic API error: {classification.user_message}"
        else:
            # Anthropic-specific error handling
            error_type = type(error).__name__
            if error_type == 'RateLimitError':
                message = f"Anthropic rate limit exceeded: {str(error)}"
                status_code = 429
            elif error_type == 'AuthenticationError':
                message = f"Anthropic authentication failed: {str(error)}"
                status_code = 401
            else:
                message = f"Anthropic API error: {str(error)}"
        
        # Create ProviderError with metadata
        provider_error = ProviderError(
            message=message,
            provider="anthropic",
            status_code=status_code,
            retry_after=retry_after
        )
        
        # Use classification for retryable flag
        provider_error.is_retryable = classification.is_retryable
        
        # Add original error reference
        provider_error.original_error = error
        
        # Add error category as an attribute
        provider_error.error_category = classification.category
        
        return provider_error
    
    @staticmethod
    def map_xai_error(error: Exception) -> ProviderError:
        """
        Map xAI-specific errors to ProviderError.
        
        Args:
            error: The xAI exception
            
        Returns:
            ProviderError with appropriate metadata
        """
        # Use ErrorClassifier for comprehensive classification
        classification = ErrorClassifier.classify_error(error, "xai")
        
        status_code = getattr(error, 'status_code', None)
        retry_after = classification.suggested_delay or ErrorMapper.get_retry_after(error)
        
        # Use classified user message or fallback
        if classification.user_message:
            message = f"xAI API error: {classification.user_message}"
        else:
            message = f"xAI API error: {str(error)}"
        
        # Create ProviderError with metadata
        provider_error = ProviderError(
            message=message,
            provider="xai",
            status_code=status_code,
            retry_after=retry_after
        )
        
        # Use classification for retryable flag
        provider_error.is_retryable = classification.is_retryable
        
        # Add original error reference
        provider_error.original_error = error
        
        # Add error category as an attribute
        provider_error.error_category = classification.category
        
        return provider_error
    
    @staticmethod
    def get_error_classification(error: ProviderError) -> Dict[str, Any]:
        """
        Get detailed error classification for logging/metrics.
        
        Args:
            error: The ProviderError to classify
            
        Returns:
            Dict with error classification details
        """
        return {
            'provider': error.provider,
            'status_code': error.status_code,
            'is_retryable': getattr(error, 'is_retryable', False),
            'retry_after': error.retry_after,
            'error_type': type(error.original_error).__name__ if hasattr(error, 'original_error') else None,
            'category': ErrorMapper._categorize_error(error)
        }
    
    @staticmethod
    def _categorize_error(error: ProviderError) -> str:
        """Categorize error for metrics/alerting."""
        # Use error_category if available from ErrorClassifier
        if hasattr(error, 'error_category'):
            return error.error_category.value
        
        # Fallback to status code categorization
        if error.status_code:
            if error.status_code == 401:
                return 'authentication'
            elif error.status_code == 429:
                return 'rate_limit'
            elif error.status_code >= 500:
                return 'server_error'
            elif error.status_code >= 400:
                return 'client_error'
        
        # Check error message
        error_msg = error.args[0].lower() if error.args else ''
        if 'timeout' in error_msg:
            return 'timeout'
        elif 'connection' in error_msg or 'network' in error_msg:
            return 'network'
        
        return 'unknown'