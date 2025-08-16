"""Mock exception classes for testing provider error handling."""

from unittest.mock import Mock
from typing import Optional, Dict, Any


class MockHTTPResponse:
    """Mock HTTP response for exception testing."""
    
    def __init__(self, status_code: int, headers: Optional[Dict[str, str]] = None):
        self.status_code = status_code
        self.headers = headers or {}


class MockOpenAIError(Exception):
    """Base mock for OpenAI errors."""
    
    def __init__(self, message: str, response: Optional[MockHTTPResponse] = None):
        super().__init__(message)
        self.message = message
        self.response = response
        if response:
            self.status_code = response.status_code
        else:
            self.status_code = None


class MockRateLimitError(MockOpenAIError):
    """Mock OpenAI RateLimitError."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        response = MockHTTPResponse(429, {"Retry-After": str(retry_after)})
        super().__init__(message, response)


class MockAuthenticationError(MockOpenAIError):
    """Mock OpenAI AuthenticationError."""
    
    def __init__(self, message: str = "Invalid API key"):
        response = MockHTTPResponse(401)
        super().__init__(message, response)


class MockBadRequestError(MockOpenAIError):
    """Mock OpenAI BadRequestError."""
    
    def __init__(self, message: str = "Invalid request"):
        response = MockHTTPResponse(400)
        super().__init__(message, response)


class MockInternalServerError(MockOpenAIError):
    """Mock OpenAI InternalServerError."""
    
    def __init__(self, message: str = "Internal server error", status_code: int = 500):
        response = MockHTTPResponse(status_code)
        super().__init__(message, response)


class MockAnthropicError(Exception):
    """Base mock for Anthropic errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = Mock()
        self.response.status_code = status_code
        self.response.headers = {}


class MockAnthropicRateLimitError(MockAnthropicError):
    """Mock Anthropic RateLimitError."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(message, 429)
        self.response.headers = {"Retry-After": str(retry_after)}


class MockAnthropicAuthenticationError(MockAnthropicError):
    """Mock Anthropic AuthenticationError."""
    
    def __init__(self, message: str = "Invalid API key"):
        super().__init__(message, 401)


class MockAnthropicBadRequestError(MockAnthropicError):
    """Mock Anthropic BadRequestError."""
    
    def __init__(self, message: str = "Invalid request"):
        super().__init__(message, 400)


class MockAnthropicServerError(MockAnthropicError):
    """Mock Anthropic Server Error."""
    
    def __init__(self, message: str = "Internal server error", status_code: int = 500):
        super().__init__(message, status_code)


class MockXAIError(Exception):
    """Base mock for xAI errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = Mock()
        self.response.status_code = status_code
        self.response.headers = {}


class MockXAIRateLimitError(MockXAIError):
    """Mock xAI RateLimitError."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(message, 429)
        self.response.headers = {"Retry-After": str(retry_after)}


class MockXAIAuthenticationError(MockXAIError):
    """Mock xAI AuthenticationError."""
    
    def __init__(self, message: str = "Invalid API key"):
        super().__init__(message, 401)


class MockXAIBadRequestError(MockXAIError):
    """Mock xAI BadRequestError."""
    
    def __init__(self, message: str = "Invalid request"):
        super().__init__(message, 400)


class MockXAIServerError(MockXAIError):
    """Mock xAI Server Error."""
    
    def __init__(self, message: str = "Internal server error", status_code: int = 500):
        super().__init__(message, status_code)