"""
Enhanced error classification system for comprehensive error handling.

This module provides detailed error classification across all providers,
enabling intelligent retry decisions and error categorization.
"""

from enum import Enum
from typing import Dict, Optional, Type, Any, Set
from dataclasses import dataclass

# Import provider-specific errors
try:
    import openai
    OPENAI_ERRORS = {
        'APIConnectionError': openai.APIConnectionError,
        'APIError': openai.APIError,
        'APITimeoutError': openai.APITimeoutError,
        'AuthenticationError': openai.AuthenticationError,
        'BadRequestError': openai.BadRequestError,
        'ConflictError': openai.ConflictError,
        'InternalServerError': openai.InternalServerError,
        'NotFoundError': openai.NotFoundError,
        'PermissionDeniedError': openai.PermissionDeniedError,
        'RateLimitError': openai.RateLimitError,
        'UnprocessableEntityError': openai.UnprocessableEntityError,
    }
except ImportError:
    OPENAI_ERRORS = {}

try:
    import anthropic
    ANTHROPIC_ERRORS = {
        'APIConnectionError': anthropic.APIConnectionError,
        'APIError': anthropic.APIError,
        'APITimeoutError': anthropic.APITimeoutError,
        'AuthenticationError': anthropic.AuthenticationError,
        'BadRequestError': anthropic.BadRequestError,
        'ConflictError': anthropic.ConflictError,
        'InternalServerError': anthropic.InternalServerError,
        'NotFoundError': anthropic.NotFoundError,
        'PermissionDeniedError': anthropic.PermissionDeniedError,
        'RateLimitError': anthropic.RateLimitError,
        'UnprocessableEntityError': anthropic.UnprocessableEntityError,
    }
except ImportError:
    ANTHROPIC_ERRORS = {}


class ErrorCategory(Enum):
    """Standard error categories across all providers."""
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    SERVER_ERROR = "server_error"
    NETWORK = "network"
    TIMEOUT = "timeout"
    CONTENT_FILTER = "content_filter"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


@dataclass
class ErrorClassification:
    """Detailed error classification."""
    category: ErrorCategory
    is_retryable: bool
    suggested_delay: Optional[float] = None
    user_message: Optional[str] = None
    should_reset_context: bool = False  # For streaming errors
    

class ErrorClassifier:
    """Enhanced error classification system."""
    
    # Comprehensive error mappings by provider
    ERROR_MAPPINGS = {
        'openai': {
            # Authentication errors
            'AuthenticationError': {
                'category': ErrorCategory.AUTHENTICATION,
                'retryable': False,
                'message': 'Invalid API key or authentication failed'
            },
            # Rate limit errors
            'RateLimitError': {
                'category': ErrorCategory.RATE_LIMIT,
                'retryable': True,
                'message': 'Rate limit exceeded, please wait before retrying'
            },
            # Client errors
            'BadRequestError': {
                'category': ErrorCategory.VALIDATION,
                'retryable': False,
                'message': 'Invalid request parameters'
            },
            'NotFoundError': {
                'category': ErrorCategory.NOT_FOUND,
                'retryable': False,
                'message': 'Resource not found'
            },
            'PermissionDeniedError': {
                'category': ErrorCategory.PERMISSION_DENIED,
                'retryable': False,
                'message': 'Permission denied for this operation'
            },
            'UnprocessableEntityError': {
                'category': ErrorCategory.VALIDATION,
                'retryable': False,
                'message': 'Request could not be processed'
            },
            'ConflictError': {
                'category': ErrorCategory.CONFLICT,
                'retryable': False,
                'message': 'Request conflicts with current state'
            },
            # Server errors
            'InternalServerError': {
                'category': ErrorCategory.SERVER_ERROR,
                'retryable': True,
                'message': 'Internal server error, please retry'
            },
            # Network errors
            'APIConnectionError': {
                'category': ErrorCategory.NETWORK,
                'retryable': True,
                'message': 'Network connection error'
            },
            'APITimeoutError': {
                'category': ErrorCategory.TIMEOUT,
                'retryable': True,
                'message': 'Request timed out'
            },
            # Generic API error
            'APIError': {
                'category': ErrorCategory.UNKNOWN,
                'retryable': True,
                'message': 'API error occurred'
            },
        },
        'anthropic': {
            # Similar mappings for Anthropic
            'AuthenticationError': {
                'category': ErrorCategory.AUTHENTICATION,
                'retryable': False,
                'message': 'Invalid Anthropic API key'
            },
            'RateLimitError': {
                'category': ErrorCategory.RATE_LIMIT,
                'retryable': True,
                'message': 'Anthropic rate limit exceeded'
            },
            'BadRequestError': {
                'category': ErrorCategory.VALIDATION,
                'retryable': False,
                'message': 'Invalid request to Anthropic API'
            },
            'NotFoundError': {
                'category': ErrorCategory.NOT_FOUND,
                'retryable': False,
                'message': 'Anthropic resource not found'
            },
            'PermissionDeniedError': {
                'category': ErrorCategory.PERMISSION_DENIED,
                'retryable': False,
                'message': 'Permission denied by Anthropic'
            },
            'UnprocessableEntityError': {
                'category': ErrorCategory.VALIDATION,
                'retryable': False,
                'message': 'Anthropic could not process request'
            },
            'ConflictError': {
                'category': ErrorCategory.CONFLICT,
                'retryable': False,
                'message': 'Request conflicts with Anthropic state'
            },
            'InternalServerError': {
                'category': ErrorCategory.SERVER_ERROR,
                'retryable': True,
                'message': 'Anthropic server error'
            },
            'APIConnectionError': {
                'category': ErrorCategory.NETWORK,
                'retryable': True,
                'message': 'Failed to connect to Anthropic'
            },
            'APITimeoutError': {
                'category': ErrorCategory.TIMEOUT,
                'retryable': True,
                'message': 'Anthropic request timed out'
            },
            'APIError': {
                'category': ErrorCategory.UNKNOWN,
                'retryable': True,
                'message': 'Anthropic API error'
            },
        },
        'xai': {
            # xAI uses similar error structure to OpenAI
            'AuthenticationError': {
                'category': ErrorCategory.AUTHENTICATION,
                'retryable': False,
                'message': 'Invalid xAI API key'
            },
            'RateLimitError': {
                'category': ErrorCategory.RATE_LIMIT,
                'retryable': True,
                'message': 'xAI rate limit exceeded'
            },
            'BadRequestError': {
                'category': ErrorCategory.VALIDATION,
                'retryable': False,
                'message': 'Invalid xAI request'
            },
            'InternalServerError': {
                'category': ErrorCategory.SERVER_ERROR,
                'retryable': True,
                'message': 'xAI server error'
            },
            'APIConnectionError': {
                'category': ErrorCategory.NETWORK,
                'retryable': True,
                'message': 'xAI connection error'
            },
            'APITimeoutError': {
                'category': ErrorCategory.TIMEOUT,
                'retryable': True,
                'message': 'xAI request timeout'
            },
        }
    }
    
    # Error patterns for string matching
    ERROR_PATTERNS = {
        # Rate limit patterns
        'rate_limit': {
            'patterns': ['rate limit', 'too many requests', 'quota exceeded', 
                        'too_many_requests', 'rate_limit_exceeded', 'throttled',
                        'retry later', 'request limit', 'api limit', 'usage limit',
                        'limit reached', 'exceeded quota', 'try again later'],
            'category': ErrorCategory.RATE_LIMIT,
            'retryable': True
        },
        # Authentication patterns
        'authentication': {
            'patterns': ['invalid api key', 'authentication failed', 'unauthorized',
                        'invalid_api_key', 'auth_error'],
            'category': ErrorCategory.AUTHENTICATION,
            'retryable': False
        },
        # Validation patterns
        'validation': {
            'patterns': ['invalid request', 'bad request', 'validation error',
                        'invalid_request', 'context_length_exceeded'],
            'category': ErrorCategory.VALIDATION,
            'retryable': False
        },
        # Server error patterns
        'server_error': {
            'patterns': ['server error', 'internal error', 'service unavailable',
                        'engine_overloaded', 'server_error'],
            'category': ErrorCategory.SERVER_ERROR,
            'retryable': True
        },
        # Network patterns
        'network': {
            'patterns': ['connection error', 'network error', 'dns resolution',
                        'connection refused', 'connection_error'],
            'category': ErrorCategory.NETWORK,
            'retryable': True
        },
        # Timeout patterns
        'timeout': {
            'patterns': ['timeout', 'timed out', 'request timeout', 'read timeout'],
            'category': ErrorCategory.TIMEOUT,
            'retryable': True
        },
        # Content filter patterns
        'content_filter': {
            'patterns': ['content filter', 'content_filter', 'safety filter',
                        'harmful content', 'content policy'],
            'category': ErrorCategory.CONTENT_FILTER,
            'retryable': False
        }
    }
    
    # Retryable status codes
    RETRYABLE_STATUS_CODES: Set[int] = {429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
    NON_RETRYABLE_STATUS_CODES: Set[int] = {400, 401, 403, 404, 405, 409, 410, 422}
    
    @classmethod
    def classify_error(cls, error: Exception, provider: str) -> ErrorClassification:
        """
        Classify an error with detailed metadata.
        
        Args:
            error: The exception to classify
            provider: The provider name (openai, anthropic, xai)
            
        Returns:
            ErrorClassification with category, retry info, and messaging
        """
        # Try provider-specific classification first
        if provider == "openai":
            return cls._classify_openai_error(error)
        elif provider == "anthropic":
            return cls._classify_anthropic_error(error)
        elif provider == "xai":
            return cls._classify_xai_error(error)
        
        # Fallback to generic classification
        return cls._classify_generic_error(error)
    
    @classmethod
    def _classify_openai_error(cls, error: Exception) -> ErrorClassification:
        """Classify OpenAI-specific errors."""
        error_type = type(error).__name__
        
        # Check if it's a known OpenAI error type
        if error_type in cls.ERROR_MAPPINGS['openai']:
            mapping = cls.ERROR_MAPPINGS['openai'][error_type]
            return ErrorClassification(
                category=mapping['category'],
                is_retryable=mapping['retryable'],
                user_message=mapping['message'],
                suggested_delay=cls._get_retry_delay(error)
            )
        
        # Check for mock error types (for testing)
        if 'RateLimitError' in error_type:
            return ErrorClassification(
                category=ErrorCategory.RATE_LIMIT,
                is_retryable=True,
                user_message='Rate limit exceeded, please wait before retrying',
                suggested_delay=cls._get_retry_delay(error)
            )
        elif 'AuthenticationError' in error_type:
            return ErrorClassification(
                category=ErrorCategory.AUTHENTICATION,
                is_retryable=False,
                user_message='Invalid API key or authentication failed',
                suggested_delay=None
            )
        elif 'BadRequestError' in error_type:
            return ErrorClassification(
                category=ErrorCategory.VALIDATION,
                is_retryable=False,
                user_message='Invalid request parameters',
                suggested_delay=None
            )
        elif 'InternalServerError' in error_type:
            return ErrorClassification(
                category=ErrorCategory.SERVER_ERROR,
                is_retryable=True,
                user_message='Internal server error, please retry',
                suggested_delay=cls._get_retry_delay(error)
            )
        
        # Fall back to generic classification
        return cls._classify_generic_error(error)
    
    @classmethod
    def _classify_anthropic_error(cls, error: Exception) -> ErrorClassification:
        """Classify Anthropic-specific errors."""
        error_type = type(error).__name__
        
        # Check if it's a known Anthropic error type
        if error_type in cls.ERROR_MAPPINGS['anthropic']:
            mapping = cls.ERROR_MAPPINGS['anthropic'][error_type]
            return ErrorClassification(
                category=mapping['category'],
                is_retryable=mapping['retryable'],
                user_message=mapping['message'],
                suggested_delay=cls._get_retry_delay(error)
            )
        
        # Fall back to generic classification
        return cls._classify_generic_error(error)
    
    @classmethod
    def _classify_xai_error(cls, error: Exception) -> ErrorClassification:
        """Classify xAI-specific errors."""
        error_type = type(error).__name__
        
        # Check if it's a known xAI error type
        if error_type in cls.ERROR_MAPPINGS['xai']:
            mapping = cls.ERROR_MAPPINGS['xai'][error_type]
            return ErrorClassification(
                category=mapping['category'],
                is_retryable=mapping['retryable'],
                user_message=mapping['message'],
                suggested_delay=cls._get_retry_delay(error)
            )
        
        # Fall back to generic classification
        return cls._classify_generic_error(error)
    
    @classmethod
    def _classify_generic_error(cls, error: Exception) -> ErrorClassification:
        """Generic error classification based on attributes and patterns."""
        # Check status code
        status_code = getattr(error, 'status_code', None)
        if status_code:
            if status_code in cls.RETRYABLE_STATUS_CODES:
                category = cls._categorize_by_status_code(status_code)
                return ErrorClassification(
                    category=category,
                    is_retryable=True,
                    suggested_delay=cls._get_retry_delay(error)
                )
            elif status_code in cls.NON_RETRYABLE_STATUS_CODES:
                category = cls._categorize_by_status_code(status_code)
                return ErrorClassification(
                    category=category,
                    is_retryable=False
                )
        
        # Check error message patterns
        try:
            error_str = str(error).lower()
        except Exception:
            # If str() fails, try to get the message another way
            error_str = getattr(error, 'message', '').lower() if hasattr(error, 'message') else ''
        
        # Check patterns in priority order (timeout before network)
        pattern_priority = ['timeout', 'rate_limit', 'authentication', 'content_filter', 
                          'server_error', 'validation', 'network']
        
        for pattern_key in pattern_priority:
            if pattern_key in cls.ERROR_PATTERNS:
                pattern_info = cls.ERROR_PATTERNS[pattern_key]
                if any(pattern in error_str for pattern in pattern_info['patterns']):
                    return ErrorClassification(
                        category=pattern_info['category'],
                        is_retryable=pattern_info['retryable'],
                        suggested_delay=cls._get_retry_delay(error)
                    )
        
        # Default classification
        return ErrorClassification(
            category=ErrorCategory.UNKNOWN,
            is_retryable=False,
            user_message="An unknown error occurred"
        )
    
    @classmethod
    def _categorize_by_status_code(cls, status_code: int) -> ErrorCategory:
        """Categorize error based on HTTP status code."""
        if status_code == 401:
            return ErrorCategory.AUTHENTICATION
        elif status_code == 403:
            return ErrorCategory.PERMISSION_DENIED
        elif status_code == 404:
            return ErrorCategory.NOT_FOUND
        elif status_code == 409:
            return ErrorCategory.CONFLICT
        elif status_code == 429:
            return ErrorCategory.RATE_LIMIT
        elif status_code >= 500:
            return ErrorCategory.SERVER_ERROR
        elif status_code >= 400:
            return ErrorCategory.VALIDATION
        else:
            return ErrorCategory.UNKNOWN
    
    @classmethod
    def _get_retry_delay(cls, error: Exception) -> Optional[float]:
        """Extract retry delay from error if available."""
        # Check for retry_after attribute first (most direct)
        if hasattr(error, 'retry_after') and error.retry_after is not None:
            return float(error.retry_after)
        
        # Check for Retry-After header
        if hasattr(error, 'response') and hasattr(error.response, 'headers'):
            retry_after = error.response.headers.get('Retry-After')
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        
        # Default delays by category
        error_type = type(error).__name__
        if 'RateLimit' in error_type:
            return 60.0  # Default 1 minute for rate limits
        elif 'Timeout' in error_type:
            return 5.0   # Default 5 seconds for timeouts
        elif 'Server' in error_type:
            return 10.0  # Default 10 seconds for server errors
        
        return None