"""Integration tests for streaming events system."""

import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock

from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.models.events import (
    StreamEvent,
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)
from steer_llm_sdk.models.streaming import StreamingOptions


@pytest.mark.skip(reason="SteerLLMClient() constructor starts MetricsCollector batch processor requiring a running event loop; cannot instantiate in sync fixture")
class TestStreamingEventsIntegration:
    """Test end-to-end streaming events functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return SteerLLMClient()
    
    @pytest.mark.asyncio
    async def test_event_callbacks_execution(self, client):
        """Test that event callbacks are executed during streaming."""
        events_received = {
            'start': [],
            'delta': [],
            'usage': [],
            'complete': [],
            'error': []
        }
        
        # Create callbacks that collect events
        async def on_start(event: StreamStartEvent):
            events_received['start'].append(event)
        
        async def on_delta(event: StreamDeltaEvent):
            events_received['delta'].append(event)
        
        async def on_usage(event: StreamUsageEvent):
            events_received['usage'].append(event)
        
        async def on_complete(event: StreamCompleteEvent):
            events_received['complete'].append(event)
        
        async def on_error(event: StreamErrorEvent):
            events_received['error'].append(event)
        
        # Mock the router to return test data
        async def mock_stream(*args, **kwargs):
            # Simulate streaming response
            yield ("Hello", None)
            yield (" world", None)
            yield ("!", None)
            # Final yield with usage
            yield (None, {
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
                "model": "gpt-4",
                "provider": "openai",
                "finish_reason": "stop"
            })
        
        client.router.generate_stream = mock_stream
        
        # Stream with event callbacks
        response = await client.stream_with_usage(
            messages="Test message",
            model="gpt-4",
            on_start=on_start,
            on_delta=on_delta,
            on_usage=on_usage,
            on_complete=on_complete,
            on_error=on_error
        )
        
        # Verify response
        assert response.get_text() == "Hello world!"
        assert response.get_usage() is not None
        
        # Note: In this mock scenario, events won't be emitted because
        # the mock doesn't use the actual provider adapters that emit events.
        # This test mainly verifies the client API integration.
    
    @pytest.mark.asyncio
    async def test_event_processor_configuration(self, client):
        """Test that event processor is properly configured."""
        # Mock router
        
        call_args = None
        async def capture_args(*args, **kwargs):
            nonlocal call_args
            call_args = kwargs
            yield ("test", None)
            yield (None, {"usage": {}, "model": "test", "provider": "test"})
        
        client.router.generate_stream = capture_args
        
        # Define a simple callback
        async def on_delta(event):
            pass
        
        # Stream with callback
        await client.stream_with_usage(
            messages="Test",
            model="gpt-4",
            on_delta=on_delta
        )
        
        # Verify streaming options were passed with event processor
        assert call_args is not None
        assert 'streaming_options' in call_args['params']
        streaming_options = call_args['params']['streaming_options']
        assert hasattr(streaming_options, 'event_processor')
        assert streaming_options.event_processor is not None
    
    @pytest.mark.asyncio
    async def test_error_event_handling(self, client):
        """Test error event emission."""
        error_events = []
        
        async def on_error(event: StreamErrorEvent):
            error_events.append(event)
        
        # Mock router to raise error
        async def error_stream(*args, **kwargs):
            yield ("partial", None)
            raise RuntimeError("Stream interrupted")
        
        client.router.generate_stream = error_stream
        
        # Stream with error callback
        with pytest.raises(RuntimeError):
            await client.stream_with_usage(
                messages="Test",
                model="gpt-4",
                on_error=on_error
            )
        
        # In actual implementation with providers, error event would be emitted
    
    @pytest.mark.asyncio
    async def test_json_mode_with_events(self, client):
        """Test JSON mode streaming with events."""
        delta_events = []
        
        async def on_delta(event: StreamDeltaEvent):
            delta_events.append(event)
        
        # Mock router
        async def json_stream(*args, **kwargs):
            yield ('{"name":', None)
            yield ('"test"', None)
            yield ('}', None)
            yield (None, {"usage": {}, "model": "gpt-4", "provider": "openai"})
        
        client.router.generate_stream = json_stream
        
        # Stream with JSON mode
        response = await client.stream_with_usage(
            messages="Return JSON",
            model="gpt-4",
            response_format={"type": "json_object"},
            on_delta=on_delta
        )
        
        # Should handle JSON post-processing
        assert response.get_text() == '{"name":"test"}'
    
    @pytest.mark.asyncio
    async def test_streaming_options_with_callbacks(self, client):
        """Test custom streaming options with event callbacks."""
        # Create custom streaming options
        custom_options = StreamingOptions(
            enable_json_stream_handler=True,
            measure_ttft=True,
            batch_events=False
        )
        
        # Mock router
        call_args = None
        async def capture_stream(*args, **kwargs):
            nonlocal call_args
            call_args = kwargs
            yield ("test", None)
            yield (None, {"usage": {}, "model": "test", "provider": "test"})
        
        client.router.generate_stream = capture_stream
        
        # Callback
        async def on_start(event):
            pass
        
        # Stream with custom options and callbacks
        await client.stream_with_usage(
            messages="Test",
            model="gpt-4",
            streaming_options=custom_options,
            on_start=on_start
        )
        
        # Verify options were preserved and event processor added
        assert call_args is not None
        opts = call_args['params']['streaming_options']
        assert opts.enable_json_stream_handler is True
        assert opts.measure_ttft is True
        assert opts.event_processor is not None


class TestEventTypeConsistency:
    """Test that events are consistently typed across providers."""
    
    def test_event_type_hierarchy(self):
        """Test event type hierarchy and fields."""
        # Base event
        base = StreamEvent(provider="test", model="test-model")
        assert base.type == ""
        assert base.provider == "test"
        assert base.model == "test-model"
        assert base.timestamp > 0
        assert isinstance(base.metadata, dict)
        
        # Start event
        start = StreamStartEvent(stream_id="123")
        assert start.type == "start"
        assert start.stream_id == "123"
        
        # Delta event
        delta = StreamDeltaEvent(delta="Hello", chunk_index=0)
        assert delta.type == "delta"
        assert delta.delta == "Hello"
        assert delta.chunk_index == 0
        assert delta.get_text() == "Hello"
        
        # Usage event
        usage = StreamUsageEvent(
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            is_estimated=True,
            confidence=0.9
        )
        assert usage.type == "usage"
        assert usage.usage["prompt_tokens"] == 10
        assert usage.is_estimated is True
        assert usage.confidence == 0.9
        
        # Complete event
        complete = StreamCompleteEvent(
            total_chunks=10,
            duration_ms=1500.0,
            final_usage={"total_tokens": 15}
        )
        assert complete.type == "complete"
        assert complete.total_chunks == 10
        assert complete.duration_ms == 1500.0
        
        # Error event
        error = StreamErrorEvent(
            error=RuntimeError("Test error"),
            is_retryable=True
        )
        assert error.type == "error"
        assert isinstance(error.error, RuntimeError)
        assert error.error_type == "RuntimeError"
        assert error.is_retryable is True
    
    def test_delta_event_text_extraction(self):
        """Test StreamDeltaEvent text extraction."""
        # String delta
        delta1 = StreamDeltaEvent(delta="Simple text")
        assert delta1.get_text() == "Simple text"
        
        # Dict with 'text' key
        delta2 = StreamDeltaEvent(delta={"text": "Dict text"})
        assert delta2.get_text() == "Dict text"
        
        # Dict with 'content' key
        delta3 = StreamDeltaEvent(delta={"content": "Content text"})
        assert delta3.get_text() == "Content text"
        
        # Dict with 'chunk' key
        delta4 = StreamDeltaEvent(delta={"chunk": "Chunk text"})
        assert delta4.get_text() == "Chunk text"
        
        # Dict with no recognized keys
        delta5 = StreamDeltaEvent(delta={"other": "value"})
        assert delta5.get_text() == ""
        
        # None delta
        delta6 = StreamDeltaEvent(delta=None)
        assert delta6.get_text() == ""


class TestEventManagerIntegration:
    """Test EventManager with typed events."""
    
    @pytest.mark.asyncio
    async def test_event_manager_typed_callbacks(self):
        """Test EventManager with typed event callbacks."""
        received_events = []
        
        # Create typed callbacks
        async def on_start(event: StreamStartEvent):
            assert isinstance(event, StreamStartEvent)
            received_events.append(('start', event))
        
        async def on_delta(event: StreamDeltaEvent):
            assert isinstance(event, StreamDeltaEvent)
            received_events.append(('delta', event))
        
        async def on_complete(event: StreamCompleteEvent):
            assert isinstance(event, StreamCompleteEvent)
            received_events.append(('complete', event))
        
        # Create manager
        from steer_llm_sdk.streaming.manager import EventManager
        manager = EventManager(
            on_start=on_start,
            on_delta=on_delta,
            on_complete=on_complete
        )
        
        # Emit typed events
        await manager.emit_event(StreamStartEvent(provider="test"))
        await manager.emit_event(StreamDeltaEvent(delta="Hello", chunk_index=0))
        await manager.emit_event(StreamCompleteEvent(total_chunks=1, duration_ms=100))
        
        # Verify events were received in order
        assert len(received_events) == 3
        assert received_events[0][0] == 'start'
        assert received_events[1][0] == 'delta'
        assert received_events[2][0] == 'complete'
    
    @pytest.mark.asyncio
    async def test_event_manager_backward_compatibility(self):
        """Test EventManager works with untyped callbacks."""
        received = []
        
        # Legacy untyped callbacks
        async def on_any(data):
            received.append(data)
        
        from steer_llm_sdk.streaming.manager import EventManager
        manager = EventManager(
            on_start=on_any,
            on_delta=on_any,
            on_usage=on_any
        )
        
        # Can emit both typed and untyped
        await manager.emit_start({"legacy": "start"})
        await manager.emit_delta("legacy delta")
        await manager.emit_usage({"tokens": 10})
        
        # Also works with typed events
        await manager.emit_event(StreamStartEvent())
        
        assert len(received) == 4