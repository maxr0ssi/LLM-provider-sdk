"""Error mapping for agent runtime integrations.

This module provides utilities for mapping provider-specific
errors to our normalized error types.
"""

from typing import Optional, Dict, Any
import re

from ...providers.base import ProviderError
from ...reliability.error_classifier import ErrorCategory


class SchemaError(ProviderError):
    """Error for JSON schema validation failures."""
    
    def __init__(
        self,
        message: str,
        pointer_path: Optional[str] = None,
        schema_path: Optional[str] = None,
        instance: Optional[Any] = None
    ):
        super().__init__(message, provider="schema", status_code=422)
        self.pointer_path = pointer_path
        self.schema_path = schema_path
        self.instance = instance
        self.is_retryable = False  # Schema errors are not retryable


def map_openai_agents_error(error: Exception) -> ProviderError:
    """Map OpenAI Agents SDK errors to ProviderError.
    
    Args:
        error: Exception from OpenAI Agents SDK
        
    Returns:
        Normalized ProviderError with retry metadata
    """
    error_str = str(error)
    error_type = type(error).__name__
    
    # Check if it's an OpenAI SDK error (from underlying openai package)
    # The Agents SDK often wraps errors from the base OpenAI SDK
    if hasattr(error, '__cause__') and error.__cause__:
        # Check if the cause is an OpenAI error
        cause_type = type(error.__cause__).__name__
        if 'openai' in str(type(error.__cause__).__module__):
            # Use the underlying OpenAI error for better classification
            error = error.__cause__
            error_str = str(error)
            error_type = cause_type
    
    # Check for guardrail errors (Agents SDK specific)
    if "guardrail" in error_str.lower() or "blocked" in error_str.lower():
        return SchemaError(
            message=f"Agent guardrail blocked output: {error_str}",
            pointer_path=None
        )
    
    # Check for tool execution errors
    if "tool" in error_str.lower() and ("failed" in error_str.lower() or "error" in error_str.lower()):
        provider_error = ProviderError(
            message=f"Tool execution failed: {error_str}",
            provider="openai_agents",
            status_code=500
        )
        provider_error.is_retryable = False  # Tool errors usually not retryable
        provider_error.error_category = ErrorCategory.UNKNOWN
        return provider_error
    
    # Check for schema validation errors
    if "schema" in error_str.lower() or "validation" in error_str.lower():
        # Extract JSON pointer if available
        pointer_match = re.search(r"at\s+['\"]?(#/[^'\"\\s]+)", error_str)
        pointer_path = pointer_match.group(1) if pointer_match else None
        
        return SchemaError(
            message=error_str,
            pointer_path=pointer_path
        )
    
    # Map based on error type and message patterns
    status_code = 500
    is_retryable = False
    retry_after = None
    error_category = ErrorCategory.UNKNOWN
    
    # Authentication errors
    if "authentication" in error_str.lower() or "unauthorized" in error_str.lower():
        status_code = 401
        error_category = ErrorCategory.AUTHENTICATION
    
    # Rate limit errors
    elif "rate limit" in error_str.lower() or "too many requests" in error_str.lower():
        status_code = 429
        is_retryable = True
        error_category = ErrorCategory.RATE_LIMIT
        
        # Try to extract retry-after
        retry_match = re.search(r"retry[_-]?after[:\s]+(\d+)", error_str, re.IGNORECASE)
        if retry_match:
            retry_after = int(retry_match.group(1))
    
    # Quota/budget errors
    elif "quota" in error_str.lower() or "budget" in error_str.lower():
        status_code = 429
        error_category = ErrorCategory.RATE_LIMIT  # Use RATE_LIMIT for quota
    
    # Invalid request errors
    elif "invalid" in error_str.lower() or "bad request" in error_str.lower():
        status_code = 400
        error_category = ErrorCategory.VALIDATION
    
    # Model not found
    elif "model" in error_str.lower() and "not found" in error_str.lower():
        status_code = 404
        error_category = ErrorCategory.NOT_FOUND
    
    # Timeout errors
    elif "timeout" in error_str.lower() or "timed out" in error_str.lower():
        status_code = 504
        is_retryable = True
        error_category = ErrorCategory.TIMEOUT
    
    # Network/connection errors
    elif any(term in error_str.lower() for term in ["connection", "network", "dns"]):
        status_code = 503
        is_retryable = True
        error_category = ErrorCategory.NETWORK
    
    # Server errors
    elif "server error" in error_str.lower() or "internal error" in error_str.lower():
        status_code = 500
        is_retryable = True
        error_category = ErrorCategory.SERVER_ERROR
    
    # Service unavailable
    elif "unavailable" in error_str.lower() or "maintenance" in error_str.lower():
        status_code = 503
        is_retryable = True
        error_category = ErrorCategory.SERVER_ERROR  # Use SERVER_ERROR for unavailable
    
    # Agent-specific errors
    elif "agent" in error_str.lower() and "not found" in error_str.lower():
        status_code = 404
        error_category = ErrorCategory.NOT_FOUND
    
    # Handoff errors (Agents SDK specific)
    elif "handoff" in error_str.lower():
        status_code = 400
        error_category = ErrorCategory.VALIDATION
    
    # Create ProviderError with metadata
    provider_error = ProviderError(
        message=error_str,
        provider="openai_agents",
        status_code=status_code,
        retry_after=retry_after
    )
    provider_error.is_retryable = is_retryable
    
    # Add error category for metrics
    provider_error.error_category = error_category
    
    # Preserve original error type
    provider_error.original_error_type = error_type
    
    return provider_error


def extract_validation_details(error: Exception) -> Dict[str, Any]:
    """Extract detailed validation information from an error.
    
    Args:
        error: Validation error
        
    Returns:
        Dictionary with validation details
    """
    details = {
        "error_type": type(error).__name__,
        "message": str(error)
    }
    
    # Try to extract JSON schema validation details
    if hasattr(error, "schema_path"):
        details["schema_path"] = list(error.schema_path)
    
    if hasattr(error, "instance"):
        details["instance"] = error.instance
    
    if hasattr(error, "validator"):
        details["validator"] = error.validator
    
    if hasattr(error, "validator_value"):
        details["validator_value"] = error.validator_value
    
    # Extract pointer path from message
    pointer_match = re.search(r"at\s+['\"]?(#/[^'\"\\s]+)", str(error))
    if pointer_match:
        details["pointer_path"] = pointer_match.group(1)
    
    return details