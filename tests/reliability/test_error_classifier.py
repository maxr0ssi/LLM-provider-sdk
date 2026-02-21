"""
Comprehensive tests for the ErrorClassifier system.

Tests all known error types for each provider and verifies
correct classification, retry behavior, and error categorization.
"""

import pytest
from unittest.mock import MagicMock, Mock
import httpx

from steer_llm_sdk.reliability.error_classifier import (
    ErrorClassifier, ErrorCategory, ErrorClassification
)
from steer_llm_sdk.providers.errors import ErrorMapper
from steer_llm_sdk.providers.base import ProviderError

# Import mock exceptions for testing
from tests.helpers.mock_exceptions import (
    MockOpenAIError, MockRateLimitError, MockAuthenticationError,
    MockBadRequestError, MockInternalServerError,
    MockAnthropicError, MockAnthropicRateLimitError,
    MockAnthropicAuthenticationError, MockAnthropicBadRequestError,
    MockAnthropicServerError,
    MockXAIError, MockXAIRateLimitError, MockXAIAuthenticationError,
    MockXAIBadRequestError, MockXAIServerError
)


class TestErrorClassifier:
    """Test the ErrorClassifier functionality."""
    
    def test_openai_rate_limit_classification(self):
        """Test OpenAI rate limit error classification."""
        error = MockRateLimitError("Rate limit exceeded", retry_after=60)
        classification = ErrorClassifier.classify_error(error, "openai")
        
        assert classification.category == ErrorCategory.RATE_LIMIT
        assert classification.is_retryable is True
        assert classification.suggested_delay == 60.0
        assert classification.user_message is not None
        
    def test_openai_authentication_classification(self):
        """Test OpenAI authentication error classification."""
        error = MockAuthenticationError("Invalid API key")
        classification = ErrorClassifier.classify_error(error, "openai")
        
        assert classification.category == ErrorCategory.AUTHENTICATION
        assert classification.is_retryable is False
        assert classification.user_message is not None
        
    def test_openai_server_error_classification(self):
        """Test OpenAI server error classification."""
        error = MockInternalServerError("Internal server error", status_code=500)
        classification = ErrorClassifier.classify_error(error, "openai")
        
        assert classification.category == ErrorCategory.SERVER_ERROR
        assert classification.is_retryable is True
        
    def test_anthropic_rate_limit_classification(self):
        """Test Anthropic rate limit error classification."""
        error = MockAnthropicRateLimitError("Rate limit exceeded", retry_after=30)
        classification = ErrorClassifier.classify_error(error, "anthropic")
        
        assert classification.category == ErrorCategory.RATE_LIMIT
        assert classification.is_retryable is True
        assert classification.suggested_delay == 30.0
        
    def test_xai_authentication_classification(self):
        """Test xAI authentication error classification."""
        error = MockXAIAuthenticationError("Invalid xAI API key")
        classification = ErrorClassifier.classify_error(error, "xai")
        
        assert classification.category == ErrorCategory.AUTHENTICATION
        assert classification.is_retryable is False
        
    def test_timeout_error_classification(self):
        """Test timeout error classification."""
        error = httpx.TimeoutException("Request timed out")
        
        for provider in ["openai", "anthropic", "xai"]:
            classification = ErrorClassifier.classify_error(error, provider)
            assert classification.category == ErrorCategory.TIMEOUT
            assert classification.is_retryable is True
            
    def test_connection_error_classification(self):
        """Test connection error classification."""
        error = httpx.ConnectError("Connection refused")
        
        for provider in ["openai", "anthropic", "xai"]:
            classification = ErrorClassifier.classify_error(error, provider)
            assert classification.category == ErrorCategory.NETWORK
            assert classification.is_retryable is True
            
    def test_error_pattern_detection(self):
        """Test error classification by pattern matching."""
        test_cases = [
            ("Rate limit exceeded for model", ErrorCategory.RATE_LIMIT, True),
            ("Too many requests, please retry", ErrorCategory.RATE_LIMIT, True),
            ("Invalid API key provided", ErrorCategory.AUTHENTICATION, False),
            ("Connection error: timeout", ErrorCategory.TIMEOUT, True),
            ("Server error: overloaded", ErrorCategory.SERVER_ERROR, True),
            ("Content filter triggered", ErrorCategory.CONTENT_FILTER, False),
        ]
        
        for error_msg, expected_category, expected_retryable in test_cases:
            error = Exception(error_msg)
            classification = ErrorClassifier.classify_error(error, "openai")
            assert classification.category == expected_category
            assert classification.is_retryable == expected_retryable
            
    def test_status_code_classification(self):
        """Test classification based on HTTP status codes."""
        test_codes = {
            401: (ErrorCategory.AUTHENTICATION, False),
            403: (ErrorCategory.PERMISSION_DENIED, False),
            404: (ErrorCategory.NOT_FOUND, False),
            409: (ErrorCategory.CONFLICT, False),
            429: (ErrorCategory.RATE_LIMIT, True),
            500: (ErrorCategory.SERVER_ERROR, True),
            502: (ErrorCategory.SERVER_ERROR, True),
            503: (ErrorCategory.SERVER_ERROR, True),
            504: (ErrorCategory.SERVER_ERROR, True),
        }
        
        for status_code, (expected_category, expected_retryable) in test_codes.items():
            error = MagicMock()
            error.status_code = status_code
            error.__str__ = lambda: f"Error with status {status_code}"
            
            classification = ErrorClassifier.classify_error(error, "openai")
            assert classification.category == expected_category
            assert classification.is_retryable == expected_retryable
            
    def test_unknown_error_classification(self):
        """Test classification of unknown errors."""
        error = ValueError("Some random error")
        classification = ErrorClassifier.classify_error(error, "openai")
        
        assert classification.category == ErrorCategory.UNKNOWN
        assert classification.is_retryable is False
        
    def test_retry_delay_extraction(self):
        """Test extraction of retry delay from various error types."""
        # Error with Retry-After header
        error1 = MagicMock()
        error1.response = MagicMock()
        error1.response.headers = {"Retry-After": "45"}
        error1.retry_after = None  # Explicitly set to None
        error1.__str__ = MagicMock(return_value="Rate limit error")
        # Mock the type name to trigger rate limit classification
        type(error1).__name__ = 'RateLimitError'
        
        classification1 = ErrorClassifier.classify_error(error1, "openai")
        assert classification1.suggested_delay == 45.0
        
        # Error with retry_after attribute
        error2 = MagicMock()
        error2.retry_after = 30.0
        error2.response = None  # No response headers
        error2.__str__ = MagicMock(return_value="Rate limit error")
        # Mock the type name to trigger rate limit classification
        type(error2).__name__ = 'RateLimitError'
        
        classification2 = ErrorClassifier.classify_error(error2, "anthropic")
        assert classification2.suggested_delay == 30.0


class TestErrorMapperIntegration:
    """Test ErrorMapper integration with ErrorClassifier."""
    
    def test_openai_error_mapping_with_classifier(self):
        """Test that ErrorMapper uses ErrorClassifier correctly for OpenAI."""
        error = MockRateLimitError("Rate limit exceeded", retry_after=60)
        provider_error = ErrorMapper.map_openai_error(error)
        
        assert provider_error.is_retryable is True
        assert provider_error.retry_after == 60.0
        assert hasattr(provider_error, 'error_category')
        assert provider_error.error_category == ErrorCategory.RATE_LIMIT
        assert "Rate limit" in provider_error.args[0]
        
    def test_anthropic_error_mapping_with_classifier(self):
        """Test that ErrorMapper uses ErrorClassifier correctly for Anthropic."""
        error = MockAnthropicAuthenticationError("Invalid API key")
        provider_error = ErrorMapper.map_anthropic_error(error)
        
        assert provider_error.is_retryable is False
        assert hasattr(provider_error, 'error_category')
        assert provider_error.error_category == ErrorCategory.AUTHENTICATION
        assert provider_error.status_code == 401
        
    def test_xai_error_mapping_with_classifier(self):
        """Test that ErrorMapper uses ErrorClassifier correctly for xAI."""
        error = MockXAIServerError("Internal server error", status_code=503)
        provider_error = ErrorMapper.map_xai_error(error)
        
        assert provider_error.is_retryable is True
        assert hasattr(provider_error, 'error_category')
        assert provider_error.error_category == ErrorCategory.SERVER_ERROR
        assert provider_error.status_code == 503
        
    def test_error_classification_extraction(self):
        """Test extracting classification from mapped errors."""
        error = MockOpenAIError("Test error")
        error.status_code = 429
        
        provider_error = ErrorMapper.map_openai_error(error)
        classification = ErrorMapper.get_error_classification(provider_error)
        
        assert classification['provider'] == 'openai'
        assert classification['status_code'] == 429
        assert classification['is_retryable'] is True
        assert classification['category'] == 'rate_limit'
        
    def test_all_provider_error_types(self):
        """Test that all known error types are properly classified."""
        # OpenAI errors
        openai_errors = [
            (MockRateLimitError(), ErrorCategory.RATE_LIMIT, True),
            (MockAuthenticationError(), ErrorCategory.AUTHENTICATION, False),
            (MockBadRequestError(), ErrorCategory.VALIDATION, False),
            (MockInternalServerError(), ErrorCategory.SERVER_ERROR, True),
        ]
        
        for error, expected_category, expected_retryable in openai_errors:
            provider_error = ErrorMapper.map_openai_error(error)
            assert provider_error.error_category == expected_category
            assert provider_error.is_retryable == expected_retryable
            
        # Anthropic errors
        anthropic_errors = [
            (MockAnthropicRateLimitError(), ErrorCategory.RATE_LIMIT, True),
            (MockAnthropicAuthenticationError(), ErrorCategory.AUTHENTICATION, False),
            (MockAnthropicBadRequestError(), ErrorCategory.VALIDATION, False),
            (MockAnthropicServerError(), ErrorCategory.SERVER_ERROR, True),
        ]
        
        for error, expected_category, expected_retryable in anthropic_errors:
            provider_error = ErrorMapper.map_anthropic_error(error)
            assert provider_error.error_category == expected_category
            assert provider_error.is_retryable == expected_retryable
            
        # xAI errors
        xai_errors = [
            (MockXAIRateLimitError(), ErrorCategory.RATE_LIMIT, True),
            (MockXAIAuthenticationError(), ErrorCategory.AUTHENTICATION, False),
            (MockXAIBadRequestError(), ErrorCategory.VALIDATION, False),
            (MockXAIServerError(), ErrorCategory.SERVER_ERROR, True),
        ]
        
        for error, expected_category, expected_retryable in xai_errors:
            provider_error = ErrorMapper.map_xai_error(error)
            assert provider_error.error_category == expected_category
            assert provider_error.is_retryable == expected_retryable