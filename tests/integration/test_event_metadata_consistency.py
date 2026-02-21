"""Integration test for event metadata consistency across streaming."""

import pytest
import asyncio
from typing import List, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from steer_llm_sdk.streaming.manager import EventManager
from steer_llm_sdk.streaming.helpers import StreamingHelper
from steer_llm_sdk.streaming.adapter import StreamAdapter
from steer_llm_sdk.models.events import StreamEvent


class TestEventMetadataConsistency:
    """Test that events have consistent metadata throughout streaming."""
    
    @pytest.mark.asyncio
    async def test_metadata_consistency_in_streaming_flow(self):
        """Test that all events in a streaming flow have consistent metadata."""
        # Collect all emitted events
        collected_events: List[StreamEvent] = []
        
        async def collect_event(event):
            collected_events.append(event)
        
        # Create EventManager with metadata
        events = EventManager(
            on_start=collect_event,
            on_delta=collect_event,
            on_usage=collect_event,
            on_complete=collect_event,
            on_error=collect_event,
            request_id="test-request-123",
            trace_id="test-trace-456",
            sdk_version="test-1.0.0"
        )
        
        # Create mock stream
        async def mock_stream():
            yield {"text": "Hello "}
            yield {"text": "world!"}
            yield {"usage": {"prompt_tokens": 5, "completion_tokens": 2}}
        
        # Create adapter
        adapter = StreamAdapter("test_provider", "test_model")
        
        # Process stream
        text, usage, metrics = await StreamingHelper.collect_with_usage(
            mock_stream(),
            adapter,
            events
        )
        
        # Verify we got events
        assert len(collected_events) >= 4  # start, 2 deltas, complete
        
        # Verify all events have consistent metadata
        for event in collected_events:
            # Check request_id
            assert event.request_id == "test-request-123"
            
            # Check metadata
            assert event.metadata is not None
            assert event.metadata["sdk_version"] == "test-1.0.0"
            assert event.metadata["trace_id"] == "test-trace-456"
            
            # Check timestamp
            assert isinstance(event.timestamp, float)
            assert event.timestamp > 0
            
            # Check provider/model (might be None for some events or set by adapter)
            if event.provider is not None:
                assert event.provider == "test_provider"
            if event.model is not None:
                assert event.model == "test_model"
    
    @pytest.mark.asyncio
    async def test_metadata_consistency_with_error(self):
        """Test that error events also have consistent metadata."""
        collected_events: List[StreamEvent] = []
        
        async def collect_event(event):
            collected_events.append(event)
        
        # Create EventManager with metadata
        events = EventManager(
            on_start=collect_event,
            on_delta=collect_event,
            on_error=collect_event,
            request_id="error-test-123",
            trace_id="error-trace-456"
        )
        
        # Create mock stream that errors
        async def mock_stream():
            yield {"text": "Starting..."}
            raise ValueError("Test error")
        
        # Create adapter
        adapter = StreamAdapter("error_provider", "error_model")
        
        # Process stream and expect error
        with pytest.raises(ValueError):
            await StreamingHelper.collect_with_usage(
                mock_stream(),
                adapter,
                events
            )
        
        # Verify we got events including error
        assert len(collected_events) >= 3  # start, delta, error
        
        # Find error event
        error_event = None
        for event in collected_events:
            if hasattr(event, 'error') and event.error is not None:
                error_event = event
                break
        
        assert error_event is not None
        
        # Verify error event has consistent metadata
        assert error_event.request_id == "error-test-123"
        assert error_event.metadata["trace_id"] == "error-trace-456"
        assert error_event.metadata["sdk_version"]
    
    @pytest.mark.asyncio
    async def test_metadata_enrichment_hook_in_streaming(self):
        """Test custom enrichment hook works in streaming context."""
        collected_events: List[StreamEvent] = []
        
        async def collect_event(event):
            collected_events.append(event)
        
        # Counter for enrichment
        enrichment_counter = {"count": 0}
        
        def custom_enricher(event_type: str, kwargs: dict) -> dict:
            enrichment_counter["count"] += 1
            metadata = kwargs.setdefault("metadata", {})
            metadata["event_sequence"] = enrichment_counter["count"]
            metadata["event_type_custom"] = event_type
            return kwargs
        
        # Create EventManager with enrichment hook
        events = EventManager(
            on_start=collect_event,
            on_delta=collect_event,
            on_complete=collect_event,
            request_id="enrich-test-123",
            on_create_event=custom_enricher
        )
        
        # Create mock stream
        async def mock_stream():
            yield {"text": "Test message"}
        
        # Create adapter
        adapter = StreamAdapter("enrich_provider", "enrich_model")
        
        # Process stream
        await StreamingHelper.collect_with_usage(
            mock_stream(),
            adapter,
            events
        )
        
        # Verify enrichment was applied
        assert len(collected_events) >= 3  # start, delta, complete
        
        # Check sequence numbers
        for i, event in enumerate(collected_events):
            assert event.metadata["event_sequence"] == i + 1
            
            # Check event type custom field
            if hasattr(event, 'type'):
                assert event.metadata["event_type_custom"] == event.type
    
    @pytest.mark.asyncio
    async def test_metrics_enabled_during_streaming(self):
        """Test that metrics are tracked when enabled."""
        # Track metric calls
        metric_calls = []
        
        # Create EventManager with metrics
        events = EventManager(
            metrics_enabled=True,
            request_id="metrics-test-123"
        )
        
        # Mock the increment method
        def mock_increment(metric: str, tags=None):
            metric_calls.append((metric, tags))
        
        events._increment_metric = mock_increment
        
        # Create mock stream
        async def mock_stream():
            yield {"text": "Metrics test"}
        
        # Create adapter
        adapter = StreamAdapter("metrics_provider", "metrics_model")
        
        # Process stream  
        async for _ in StreamingHelper.stream_with_events(
            mock_stream(),
            adapter,
            events
        ):
            pass  # Just consume the stream
        
        # Verify metrics were incremented
        assert len(metric_calls) >= 3  # start, delta, complete
        
        # Check metric names and tags
        metric_names = [call[0] for call in metric_calls]
        assert 'events.created' in metric_names[0]
        
        # Check tags
        for metric, tags in metric_calls:
            assert tags is not None
            assert 'type' in tags
            assert tags['type'] in ['start', 'delta', 'complete', 'usage', 'error']