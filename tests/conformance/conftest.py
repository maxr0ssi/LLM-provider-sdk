"""Shared fixtures for conformance tests."""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Test response from OpenAI"
    response.choices[0].finish_reason = "stop"
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    response.usage.total_tokens = 15
    return response


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = "Test response from Anthropic"
    response.stop_reason = "end_turn"
    response.usage.input_tokens = 10
    response.usage.output_tokens = 5
    return response


@pytest.fixture
def mock_xai_response():
    """Mock xAI API response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Test response from xAI"
    response.choices[0].finish_reason = "stop"
    # xAI doesn't provide usage in response
    return response


@pytest.fixture
def mock_openai_stream():
    """Mock OpenAI streaming response."""
    chunks = []
    
    # First chunk with content
    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "Hello"
    chunk1.choices[0].finish_reason = None
    chunk1.usage = None
    chunks.append(chunk1)
    
    # Second chunk with content
    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = " world"
    chunk2.choices[0].finish_reason = None
    chunk2.usage = None
    chunks.append(chunk2)
    
    # Final chunk with usage
    chunk3 = MagicMock()
    chunk3.choices = [MagicMock()]
    chunk3.choices[0].delta.content = None
    chunk3.choices[0].finish_reason = "stop"
    chunk3.usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15
    )
    chunks.append(chunk3)
    
    return chunks


@pytest.fixture
def mock_anthropic_stream():
    """Mock Anthropic streaming response."""
    events = []
    
    # Content block start
    event1 = MagicMock()
    event1.type = "content_block_start"
    events.append(event1)
    
    # Content deltas
    event2 = MagicMock()
    event2.type = "content_block_delta"
    event2.delta.text = "Hello"
    events.append(event2)
    
    event3 = MagicMock()
    event3.type = "content_block_delta"
    event3.delta.text = " world"
    events.append(event3)
    
    # Message delta with usage
    event4 = MagicMock()
    event4.type = "message_delta"
    event4.usage = MagicMock(
        input_tokens=10,
        output_tokens=5
    )
    event4.delta.stop_reason = "end_turn"
    events.append(event4)
    
    # Message stop
    event5 = MagicMock()
    event5.type = "message_stop"
    events.append(event5)
    
    return events


@pytest.fixture
def mock_xai_stream():
    """Mock xAI streaming response."""
    chunks = []
    
    chunk1 = MagicMock()
    chunk1.content = "Hello"
    chunks.append((None, chunk1))
    
    chunk2 = MagicMock()
    chunk2.content = " world"
    chunks.append((None, chunk2))
    
    return chunks


@pytest.fixture
def mock_rate_limit_error():
    """Mock rate limit error."""
    error = MagicMock()
    error.status_code = 429
    error.response = MagicMock()
    error.response.headers = {"retry-after": "60"}
    error.message = "Rate limit exceeded"
    return error


@pytest.fixture
def mock_timeout_error():
    """Mock timeout error."""
    import httpx
    return httpx.TimeoutException("Request timed out")


@pytest.fixture
def mock_invalid_request_error():
    """Mock invalid request error."""
    error = MagicMock()
    error.status_code = 400
    error.message = "Invalid request: temperature must be between 0 and 2"
    return error