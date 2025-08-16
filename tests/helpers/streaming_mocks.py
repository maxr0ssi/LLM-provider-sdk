"""Helper functions for creating streaming mocks."""

from unittest.mock import MagicMock
from typing import List, Any, Optional, AsyncGenerator


async def create_openai_stream(chunks: List[str]) -> AsyncGenerator[Any, None]:
    """Create a mock OpenAI streaming response."""
    for chunk in chunks:
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = chunk
        mock_chunk.choices[0].finish_reason = None
        mock_chunk.usage = None
        yield mock_chunk
    
    # Final chunk with usage
    final_chunk = MagicMock()
    final_chunk.choices = [MagicMock()]
    final_chunk.choices[0].delta.content = None
    final_chunk.choices[0].finish_reason = "stop"
    usage_mock = MagicMock(
        prompt_tokens=10,
        completion_tokens=len(chunks) * 2,
        total_tokens=10 + len(chunks) * 2
    )
    # Add model_dump method
    usage_mock.model_dump.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": len(chunks) * 2,
        "total_tokens": 10 + len(chunks) * 2
    }
    final_chunk.usage = usage_mock
    yield final_chunk


async def create_anthropic_stream(chunks: List[str]) -> AsyncGenerator[Any, None]:
    """Create a mock Anthropic streaming response."""
    # Start event
    start_event = MagicMock()
    start_event.type = "message_start"
    yield start_event
    
    # Content chunks
    for chunk in chunks:
        event = MagicMock()
        event.type = "content_block_delta"
        event.delta = MagicMock(text=chunk)
        yield event
    
    # Usage event
    usage_event = MagicMock()
    usage_event.type = "message_delta"
    usage_mock = MagicMock(
        input_tokens=10,
        output_tokens=len(chunks) * 2
    )
    # Add cache attributes with None values
    usage_mock.cache_creation_input_tokens = None
    usage_mock.cache_read_input_tokens = None
    # Add model_dump method
    usage_mock.model_dump.return_value = {
        "input_tokens": 10,
        "output_tokens": len(chunks) * 2,
        "cache_creation_input_tokens": None,
        "cache_read_input_tokens": None
    }
    usage_event.usage = usage_mock
    usage_event.delta = MagicMock()
    usage_event.delta.stop_reason = "end_turn"
    yield usage_event
    
    # Stop event
    stop_event = MagicMock()
    stop_event.type = "message_stop"
    yield stop_event


async def create_xai_stream(chunks: List[str]) -> AsyncGenerator[Any, None]:
    """Create a mock xAI streaming response."""
    for chunk in chunks:
        mock_chunk = MagicMock()
        mock_chunk.content = chunk
        # xAI returns tuples of (response, chunk)
        yield (MagicMock(), mock_chunk)


async def create_error_stream(error: Exception) -> AsyncGenerator[Any, None]:
    """Create a stream that raises an error immediately."""
    raise error
    yield  # This will never be reached


async def create_interrupted_openai_stream(chunks_before_error: int = 2) -> AsyncGenerator[Any, None]:
    """Create a mock OpenAI streaming response that fails partway through."""
    import httpx
    
    # Yield a few chunks successfully
    chunks = ["Hello", " world", " how", " are", " you"]
    for i in range(min(chunks_before_error, len(chunks))):
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = chunks[i]
        mock_chunk.choices[0].finish_reason = None
        mock_chunk.usage = None
        yield mock_chunk
    
    # Then raise a connection error
    raise httpx.ConnectError("Connection lost during streaming")


async def create_interrupted_anthropic_stream(chunks_before_error: int = 2) -> AsyncGenerator[Any, None]:
    """Create a mock Anthropic streaming response that fails partway through."""
    import httpx
    
    # Start event
    start_event = MagicMock()
    start_event.type = "message_start"
    yield start_event
    
    # Yield a few chunks successfully
    chunks = ["Hello", " world", " how", " are", " you"]
    for i in range(min(chunks_before_error, len(chunks))):
        event = MagicMock()
        event.type = "content_block_delta"
        event.delta = MagicMock(text=chunks[i])
        yield event
    
    # Then raise a connection error
    raise httpx.ConnectError("Connection lost during streaming")


async def create_interrupted_xai_stream(chunks_before_error: int = 2) -> AsyncGenerator[Any, None]:
    """Create a mock xAI streaming response that fails partway through."""
    import httpx
    
    # Yield a few chunks successfully
    chunks = ["Hello", " world", " how", " are", " you"]
    for i in range(min(chunks_before_error, len(chunks))):
        mock_chunk = MagicMock()
        mock_chunk.content = chunks[i]
        # xAI returns tuples of (response, chunk)
        yield (MagicMock(), mock_chunk)
    
    # Then raise a connection error
    raise httpx.ConnectError("Connection lost during streaming")