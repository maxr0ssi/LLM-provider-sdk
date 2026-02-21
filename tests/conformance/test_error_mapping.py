"""Test error mapping functionality directly."""

import pytest
from unittest.mock import MagicMock
import httpx

from steer_llm_sdk.providers.errors import ErrorMapper
from steer_llm_sdk.providers.base import ProviderError


class TestErrorMapping:
    """Test the ErrorMapper functionality."""
    
    def test_rate_limit_error_is_retryable(self):
        """Test that rate limit errors are marked as retryable."""
        # Create error with 429 status code
        error = MagicMock()
        error.status_code = 429
        error.message = "Rate limit exceeded"
        
        # Test OpenAI error mapping
        provider_error = ErrorMapper.map_openai_error(error)
        assert provider_error.is_retryable is True
        assert provider_error.status_code == 429
        assert "rate limit" in str(provider_error).lower()
        
        # Test Anthropic error mapping
        provider_error = ErrorMapper.map_anthropic_error(error)
        assert provider_error.is_retryable is True
        assert provider_error.status_code == 429
        
        # Test xAI error mapping
        provider_error = ErrorMapper.map_xai_error(error)
        assert provider_error.is_retryable is True
        assert provider_error.status_code == 429
    
    def test_timeout_error_is_retryable(self):
        """Test that timeout errors are marked as retryable."""
        # Create timeout error
        error = httpx.TimeoutException("Request timed out")
        
        # Test all mappers
        for mapper_method in [ErrorMapper.map_openai_error, 
                              ErrorMapper.map_anthropic_error,
                              ErrorMapper.map_xai_error]:
            provider_error = mapper_method(error)
            assert provider_error.is_retryable is True
            assert "timed out" in str(provider_error).lower() or "timeout" in str(provider_error).lower()
    
    def test_connection_error_is_retryable(self):
        """Test that connection errors are marked as retryable."""
        # Create connection error
        error = httpx.ConnectError("Connection refused")
        
        # Test all mappers
        for mapper_method in [ErrorMapper.map_openai_error, 
                              ErrorMapper.map_anthropic_error,
                              ErrorMapper.map_xai_error]:
            provider_error = mapper_method(error)
            assert provider_error.is_retryable is True
            assert "connect" in str(provider_error).lower()
    
    def test_server_errors_are_retryable(self):
        """Test that 5xx errors are marked as retryable."""
        server_codes = [500, 502, 503, 504]
        
        for status_code in server_codes:
            error = MagicMock()
            error.status_code = status_code
            error.message = f"Server error {status_code}"
            
            # Test all mappers
            for mapper_method in [ErrorMapper.map_openai_error, 
                                  ErrorMapper.map_anthropic_error,
                                  ErrorMapper.map_xai_error]:
                provider_error = mapper_method(error)
                assert provider_error.is_retryable is True
                assert provider_error.status_code == status_code
    
    def test_client_errors_are_not_retryable(self):
        """Test that 4xx errors (except 429) are not retryable."""
        client_codes = [400, 401, 403, 404]
        
        for status_code in client_codes:
            error = MagicMock()
            error.status_code = status_code
            error.message = f"Client error {status_code}"
            
            # Test all mappers
            for mapper_method in [ErrorMapper.map_openai_error, 
                                  ErrorMapper.map_anthropic_error,
                                  ErrorMapper.map_xai_error]:
                provider_error = mapper_method(error)
                assert provider_error.is_retryable is False
                assert provider_error.status_code == status_code
    
    def test_retry_after_extraction(self):
        """Test that retry-after header is extracted correctly."""
        # Error with retry-after in headers
        error = MagicMock()
        error.status_code = 429
        error.response = MagicMock()
        error.response.headers = {"Retry-After": "60"}
        error.retry_after = None  # Ensure attribute doesn't exist initially
        
        provider_error = ErrorMapper.map_openai_error(error)
        assert provider_error.retry_after == 60.0
        
        # Error with retry_after attribute
        error2 = MagicMock()
        error2.status_code = 429
        error2.retry_after = 30.0
        error2.response = None  # No response headers
        
        provider_error2 = ErrorMapper.map_anthropic_error(error2)
        assert provider_error2.retry_after == 30.0
    
    def test_original_error_preserved(self):
        """Test that original error is preserved in ProviderError."""
        original = ValueError("Original error message")
        
        # Test all mappers
        for mapper_method in [ErrorMapper.map_openai_error, 
                              ErrorMapper.map_anthropic_error,
                              ErrorMapper.map_xai_error]:
            provider_error = mapper_method(original)
            assert provider_error.original_error is original
            assert isinstance(provider_error.original_error, ValueError)
    
    def test_rate_limit_keywords_detected(self):
        """Test that rate limit errors are detected by keywords."""
        rate_limit_messages = [
            "Rate limit exceeded",
            "Too many requests",
            "Quota exceeded",
            "rate limit",
            "TOO_MANY_REQUESTS"
        ]
        
        for message in rate_limit_messages:
            error = MagicMock()
            error.status_code = None  # No status code
            error.message = message
            # Make the mock return the message when converted to string
            # Use default arg to capture the current value of message
            error.__str__ = lambda msg=message: msg
            
            provider_error = ErrorMapper.map_openai_error(error)
            assert provider_error.is_retryable is True, f"'{message}' should be detected as rate limit"