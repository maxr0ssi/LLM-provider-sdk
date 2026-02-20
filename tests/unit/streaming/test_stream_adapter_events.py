"""Test StreamAdapter integration with EventProcessor."""

import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import MagicMock, AsyncMock

from steer_llm_sdk.streaming.adapter import StreamAdapter
from steer_llm_sdk.streaming.processor import (
    EventProcessor,
    TypeFilter,
    CorrelationTransformer,
    MetricsTransformer,
    create_event_processor
)
from steer_llm_sdk.models.events import (
    StreamEvent,
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)


class TestStreamAdapterEventIntegration:
    """Test StreamAdapter event processor integration."""
    
    @pytest.mark.asyncio
    async def test_basic_event_emission(self):
        """Test basic event emission through StreamAdapter."""
        adapter = StreamAdapter("openai", "gpt-4")
        events = []
        
        # Create processor that collects events
        async def collect_event(event: StreamEvent) -> StreamEvent:
            events.append(event)
            return event
        
        processor = EventProcessor()
        processor.process_event = collect_event
        adapter.set_event_processor(processor, "test-request-123")
        
        # Start stream
        await adapter.start_stream()
        assert len(events) == 1
        assert isinstance(events[0], StreamStartEvent)
        assert events[0].provider == "openai"
        assert events[0].model == "gpt-4"
        assert events[0].request_id == "test-request-123"
        
        # Track chunks
        await adapter.track_chunk(10, "Hello")
        assert len(events) == 2
        assert isinstance(events[1], StreamDeltaEvent)
        assert events[1].delta == "Hello"
        assert events[1].chunk_index == 0
        
        # Emit usage
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        await adapter.emit_usage(usage)
        assert len(events) == 3
        assert isinstance(events[2], StreamUsageEvent)
        assert events[2].usage == usage
        assert events[2].is_estimated is False
        
        # Complete stream
        await adapter.complete_stream(final_usage=usage)
        assert len(events) == 4
        assert isinstance(events[3], StreamCompleteEvent)
        assert events[3].total_chunks == 1
        assert events[3].final_usage == usage
    
    @pytest.mark.asyncio
    async def test_event_filtering(self):
        """Test event filtering in StreamAdapter."""
        adapter = StreamAdapter("anthropic", "claude-3")
        collected_events = []
        
        # Create processor that only processes delta events
        processor = create_event_processor(
            event_types=[StreamDeltaEvent],
            add_correlation=True
        )
        
        # Override process_event to collect
        original_process = processor.process_event
        async def collect_process(event):
            result = await original_process(event)
            if result:
                collected_events.append(result)
            return result
        processor.process_event = collect_process
        
        adapter.set_event_processor(processor)
        
        # Emit various events
        await adapter.start_stream()  # Should be filtered
        await adapter.track_chunk(5, "Hi")  # Should pass
        await adapter.track_chunk(6, "there")  # Should pass
        await adapter.complete_stream()  # Should be filtered
        
        # Only delta events should be collected
        assert len(collected_events) == 2
        assert all(isinstance(e, StreamDeltaEvent) for e in collected_events)
        assert collected_events[0].delta == "Hi"
        assert collected_events[1].delta == "there"
        
        # All should have correlation ID
        correlation_id = collected_events[0].metadata.get("correlation_id")
        assert correlation_id is not None
        assert all(e.metadata.get("correlation_id") == correlation_id for e in collected_events)
    
    @pytest.mark.asyncio
    async def test_error_event_emission(self):
        """Test error event emission."""
        adapter = StreamAdapter("xai", "grok")
        events = []
        
        # Collect all events
        async def collect(event):
            events.append(event)
            return event
        
        processor = EventProcessor()
        processor.process_event = collect
        adapter.set_event_processor(processor)
        
        # Start and then error
        await adapter.start_stream()
        error = RuntimeError("Stream interrupted")
        await adapter.complete_stream(error=error)
        
        assert len(events) == 2
        assert isinstance(events[0], StreamStartEvent)
        assert isinstance(events[1], StreamErrorEvent)
        assert events[1].error == error
        assert events[1].error_type == "RuntimeError"
    
    @pytest.mark.asyncio
    async def test_metrics_transformer_integration(self):
        """Test metrics transformer with StreamAdapter."""
        adapter = StreamAdapter("openai", "gpt-4")
        events = []
        
        # Create processor with metrics transformer
        processor = create_event_processor(add_metrics=True)
        
        # Collect processed events
        original_process = processor.process_event
        async def collect_process(event):
            result = await original_process(event)
            if result:
                events.append(result)
            return result
        processor.process_event = collect_process
        
        adapter.set_event_processor(processor)
        
        # Stream some content
        await adapter.start_stream()
        await asyncio.sleep(0.01)  # Small delay for TTFT
        await adapter.track_chunk(5, "First")
        await adapter.track_chunk(6, "Second")
        await adapter.complete_stream()
        
        # Check metrics were added
        assert len(events) == 4
        
        # Start event should have metrics_start
        assert "metrics_start" in events[0].metadata
        
        # First delta should have TTFT
        assert "ttft" in events[1].metadata
        assert "is_first_token" in events[1].metadata
        assert events[1].metadata["is_first_token"] is True
        
        # Complete event should have summary
        assert "total_duration" in events[3].metadata
        assert "metrics_summary" in events[3].metadata
    
    @pytest.mark.asyncio
    async def test_usage_aggregation_event(self):
        """Test usage aggregation event emission."""
        adapter = StreamAdapter("xai", "grok")
        adapter.configure_usage_aggregation(
            enable=True,
            messages="Test prompt",
            aggregator_type="character"
        )
        
        events = []
        async def collect(event):
            events.append(event)
            return event
        
        processor = EventProcessor()
        processor.process_event = collect
        adapter.set_event_processor(processor)
        
        # Start stream
        await adapter.start_stream()
        
        # Track some chunks (xAI doesn't provide usage)
        await adapter.track_chunk(10, "Response 1")
        await adapter.track_chunk(15, "Response part 2")
        
        # Get aggregated usage
        usage = adapter.get_aggregated_usage()
        assert usage is not None
        
        # Emit aggregated usage
        await adapter.emit_usage(usage, is_estimated=True)
        
        # Check usage event
        usage_events = [e for e in events if isinstance(e, StreamUsageEvent)]
        assert len(usage_events) == 1
        assert usage_events[0].is_estimated is True
        assert usage_events[0].confidence < 1.0  # Character estimation has lower confidence
    
    @pytest.mark.asyncio
    async def test_json_response_format_events(self):
        """Test JSON response format in delta events."""
        adapter = StreamAdapter("openai", "gpt-4")
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        
        events = []
        processor = EventProcessor()
        processor.process_event = AsyncMock(side_effect=lambda e: events.append(e) or e)
        adapter.set_event_processor(processor)
        
        await adapter.start_stream()
        await adapter.track_chunk(10, '{"name":')
        await adapter.track_chunk(8, '"test"}')
        
        # Check delta events have is_json flag
        delta_events = [e for e in events if isinstance(e, StreamDeltaEvent)]
        assert len(delta_events) == 2
        assert all(e.is_json for e in delta_events)
    
    @pytest.mark.asyncio
    async def test_no_processor_graceful_handling(self):
        """Test StreamAdapter works without processor."""
        adapter = StreamAdapter("anthropic", "claude-3")
        
        # These should not raise errors
        await adapter.start_stream()
        await adapter.track_chunk(5, "test")
        await adapter.emit_usage({"total_tokens": 10})
        await adapter.complete_stream()
        
        # Adapter should still track metrics
        metrics = adapter.get_metrics()
        assert metrics["chunks"] == 1
        assert metrics["total_chars"] == 5