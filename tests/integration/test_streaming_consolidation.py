"""
Integration tests for the consolidated streaming architecture.

Tests the unified streaming pipeline using StreamingHelper, EventProcessor, and StreamAdapter.
"""

import asyncio
import json
from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from steer_llm_sdk.streaming.helpers import StreamingHelper
from steer_llm_sdk.streaming.adapter import StreamAdapter
from steer_llm_sdk.streaming.manager import EventManager
from steer_llm_sdk.streaming.processor import create_event_processor
from steer_llm_sdk.models.events import (
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)
from steer_llm_sdk.providers.base import ProviderError


class MockChunk:
    """Mock chunk for testing."""
    def __init__(self, text: str, usage: Optional[Dict[str, Any]] = None):
        self.text = text
        self.usage = usage


async def create_mock_stream(chunks: List[str], usage_data: Optional[Dict[str, Any]] = None, error_at: Optional[int] = None) -> AsyncGenerator:
    """Create a mock stream for testing."""
    for i, chunk in enumerate(chunks):
        if error_at is not None and i == error_at:
            error = ProviderError("Test error", provider="test", status_code=500)
            error.is_retryable = True
            raise error
        
        # Return tuple format (chunk, usage_data) on last chunk if usage provided
        if i == len(chunks) - 1 and usage_data:
            yield (chunk, {"usage": usage_data})
        else:
            yield chunk
        
        await asyncio.sleep(0.01)  # Simulate streaming delay


class TestStreamingConsolidation:
    """Test the consolidated streaming architecture."""
    
    @pytest.fixture
    def adapter(self):
        """Create a test adapter."""
        adapter = StreamAdapter("test")
        adapter.model = "test-model"
        return adapter
    
    @pytest.fixture
    def event_collector(self):
        """Create an event collector for testing."""
        class EventCollector:
            def __init__(self):
                self.events = []
                self.start_events = []
                self.delta_events = []
                self.usage_events = []
                self.complete_events = []
                self.error_events = []
            
            async def on_start(self, event: StreamStartEvent):
                self.start_events.append(event)
                self.events.append(("start", event))
            
            async def on_delta(self, event: StreamDeltaEvent):
                self.delta_events.append(event)
                self.events.append(("delta", event))
            
            async def on_usage(self, event: StreamUsageEvent):
                self.usage_events.append(event)
                self.events.append(("usage", event))
            
            async def on_complete(self, event: StreamCompleteEvent):
                self.complete_events.append(event)
                self.events.append(("complete", event))
            
            async def on_error(self, event: StreamErrorEvent):
                self.error_events.append(event)
                self.events.append(("error", event))
        
        return EventCollector()
    
    @pytest.mark.asyncio
    async def test_collect_with_usage_basic(self, adapter, event_collector):
        """Test basic collect_with_usage functionality."""
        chunks = ["Hello", " ", "world", "!"]
        usage_data = {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14
        }
        
        # Create event manager with callbacks
        events = EventManager(
            on_start=event_collector.on_start,
            on_delta=event_collector.on_delta,
            on_usage=event_collector.on_usage,
            on_complete=event_collector.on_complete,
            on_error=event_collector.on_error
        )
        
        # Use StreamingHelper to collect
        stream = create_mock_stream(chunks, usage_data)
        text, usage, metrics = await StreamingHelper.collect_with_usage(stream, adapter, events)
        
        # Verify results
        assert text == "Hello world!"
        assert usage == usage_data
        assert "chunks" in metrics
        assert metrics["chunks"] == len(chunks)
        assert "duration_seconds" in metrics
        
        # Verify events
        assert len(event_collector.start_events) == 1
        assert len(event_collector.delta_events) == len(chunks)
        assert len(event_collector.usage_events) == 1
        assert len(event_collector.complete_events) == 1
        assert len(event_collector.error_events) == 0
        
        # Verify event order
        event_types = [t for t, _ in event_collector.events]
        assert event_types[0] == "start"
        assert event_types[-1] == "complete"
        assert event_types[-2] == "usage"
    
    @pytest.mark.asyncio
    async def test_stream_with_events(self, adapter, event_collector):
        """Test stream_with_events functionality."""
        chunks = ["Stream", "ing", " ", "test"]
        
        events = EventManager(
            on_start=event_collector.on_start,
            on_delta=event_collector.on_delta,
            on_complete=event_collector.on_complete
        )
        
        # Use StreamingHelper to stream
        stream = create_mock_stream(chunks)
        collected_chunks = []
        
        async for chunk in StreamingHelper.stream_with_events(stream, adapter, events):
            collected_chunks.append(chunk)
        
        # Verify results
        assert collected_chunks == chunks
        assert len(event_collector.start_events) == 1
        assert len(event_collector.delta_events) == len(chunks)
        assert len(event_collector.complete_events) == 1
    
    @pytest.mark.asyncio
    async def test_event_processor_integration(self, adapter):
        """Test StreamingHelper with EventProcessor."""
        chunks = ["Test", " ", "processor"]
        
        # Create event processor with transformers
        processor = create_event_processor(
            add_correlation=True,
            add_timestamp=True,
            add_metrics=True
        )
        
        # Attach processor to adapter
        adapter.set_event_processor(processor)
        
        # Collect events emitted by adapter
        emitted_events = []
        
        async def collect_event(event):
            emitted_events.append(event)
        
        # Patch adapter emit_event to collect
        original_emit = adapter.emit_event
        
        async def intercept_emit(event):
            # Call original to process through pipeline
            processed = await original_emit(event)
            if processed:
                await collect_event(processed)
            return processed
        
        adapter.emit_event = intercept_emit
        
        try:
            # Use StreamingHelper
            stream = create_mock_stream(chunks)
            text, _, metrics = await StreamingHelper.collect_with_usage(stream, adapter, None)
            
            assert text == "Test processor"
            
            # Verify events were processed
            assert len(emitted_events) > 0
            
            # Check that events have metadata added by transformers
            for event in emitted_events:
                if isinstance(event, (StreamStartEvent, StreamDeltaEvent)):
                    assert "correlation_id" in event.metadata
                    assert "timestamp" in event.metadata
                    assert "datetime" in event.metadata
        finally:
            adapter.emit_event = original_emit
    
    @pytest.mark.asyncio
    async def test_json_mode_handling(self, adapter, event_collector):
        """Test JSON mode handling in consolidated streaming."""
        json_data = {"result": "success", "value": 42}
        json_str = json.dumps(json_data)
        chunks = [json_str[i:i+5] for i in range(0, len(json_str), 5)]
        
        # Configure adapter for JSON mode
        adapter.response_format = {"type": "json_object"}
        
        events = EventManager(on_delta=event_collector.on_delta)
        
        # Use StreamingHelper
        stream = create_mock_stream(chunks)
        text, _, _ = await StreamingHelper.collect_with_usage(stream, adapter, events)
        
        # Verify JSON reconstruction
        assert text == json_str
        
        # Verify is_json flag in delta events
        for event in event_collector.delta_events:
            assert event.is_json is True
    
    @pytest.mark.asyncio
    async def test_error_handling(self, adapter, event_collector):
        """Test error handling in consolidated streaming."""
        chunks = ["Part", "ial", " ", "response"]
        
        events = EventManager(
            on_start=event_collector.on_start,
            on_delta=event_collector.on_delta,
            on_error=event_collector.on_error
        )
        
        # Create stream that errors after 2 chunks
        stream = create_mock_stream(chunks, error_at=2)
        
        with pytest.raises(ProviderError) as exc_info:
            await StreamingHelper.collect_with_usage(stream, adapter, events)
        
        # Verify error event was emitted
        assert len(event_collector.error_events) == 1
        error_event = event_collector.error_events[0]
        assert error_event.error_type == "ProviderError"
        assert error_event.is_retryable is True
        
        # Verify partial collection
        assert len(event_collector.delta_events) == 2  # Got 2 chunks before error
    
    @pytest.mark.asyncio
    async def test_streaming_metrics(self, adapter):
        """Test streaming metrics collection."""
        chunks = ["First", " ", "token", " ", "test"]
        
        stream = create_mock_stream(chunks)
        _, _, metrics = await StreamingHelper.collect_with_usage(stream, adapter, None)
        
        # Verify basic metrics are tracked
        assert "chunks" in metrics
        assert metrics["chunks"] == len(chunks)
        assert "total_chars" in metrics
        assert metrics["total_chars"] == sum(len(c) for c in chunks)
        assert "duration_seconds" in metrics
        assert metrics["duration_seconds"] > 0
        assert "chunks_per_second" in metrics
        assert "chars_per_second" in metrics
    
    @pytest.mark.asyncio 
    async def test_single_usage_event(self, adapter, event_collector):
        """Test that only one usage event is emitted per stream."""
        chunks = ["Multi", " ", "usage"]
        usage_data = {
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "total_tokens": 8
        }
        
        events = EventManager(on_usage=event_collector.on_usage)
        
        # Create stream that returns usage with last chunk
        stream = create_mock_stream(chunks, usage_data)
        await StreamingHelper.collect_with_usage(stream, adapter, events)
        
        # Verify only one usage event
        assert len(event_collector.usage_events) == 1
        usage_event = event_collector.usage_events[0]
        assert usage_event.usage == usage_data
        assert usage_event.is_estimated is False
    
    @pytest.mark.asyncio
    async def test_chunk_parity(self, adapter):
        """Test that all chunks are preserved exactly."""
        # Test with various chunk patterns
        test_cases = [
            ["Simple", " ", "text"],
            ["", "Empty", "", "chunks", ""],
            ["Single"],
            ["Unicode", " ", "😀", " ", "test"],
            ["New\n", "lines\n", "preserved"]
        ]
        
        for chunks in test_cases:
            stream = create_mock_stream(chunks)
            text, _, _ = await StreamingHelper.collect_with_usage(stream, adapter, None)
            
            expected = "".join(chunks)
            assert text == expected, f"Failed for chunks: {chunks}"
    
    @pytest.mark.asyncio
    async def test_adapter_lifecycle(self, adapter):
        """Test adapter lifecycle methods are called correctly."""
        chunks = ["Life", "cycle"]
        
        # Track lifecycle calls
        start_called = False
        complete_called = False
        complete_error = None
        complete_usage = None
        
        # Patch lifecycle methods
        async def track_start():
            nonlocal start_called
            start_called = True
            await adapter._original_start()
        
        async def track_complete(error=None, final_usage=None):
            nonlocal complete_called, complete_error, complete_usage
            complete_called = True
            complete_error = error
            complete_usage = final_usage
            await adapter._original_complete(error, final_usage)
        
        adapter._original_start = adapter.start_stream
        adapter._original_complete = adapter.complete_stream
        adapter.start_stream = track_start
        adapter.complete_stream = track_complete
        
        try:
            # Success case
            stream = create_mock_stream(chunks, {"total_tokens": 10})
            await StreamingHelper.collect_with_usage(stream, adapter, None)
            
            assert start_called is True
            assert complete_called is True
            assert complete_error is None
            assert complete_usage == {"total_tokens": 10}
            
            # Reset for error case
            start_called = False
            complete_called = False
            
            # Error case
            error_stream = create_mock_stream(chunks, error_at=1)
            with pytest.raises(ProviderError):
                await StreamingHelper.collect_with_usage(error_stream, adapter, None)
            
            assert start_called is True
            assert complete_called is True
            assert complete_error is not None
            assert isinstance(complete_error, ProviderError)
        
        finally:
            adapter.start_stream = adapter._original_start
            adapter.complete_stream = adapter._original_complete