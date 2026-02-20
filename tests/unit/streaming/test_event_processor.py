"""Unit tests for event processor module."""

import pytest
import asyncio
import time
from typing import List, Optional
from unittest.mock import MagicMock, AsyncMock

from steer_llm_sdk.streaming.processor import (
    EventProcessor,
    BatchedEventProcessor,
    EventFilter,
    TypeFilter,
    ProviderFilter,
    PredicateFilter,
    CompositeFilter,
    EventTransformer,
    CorrelationTransformer,
    TimestampTransformer,
    MetricsTransformer,
    create_event_processor,
    ProcessorMetrics
)
from steer_llm_sdk.models.events import (
    StreamEvent,
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)


class TestEventFilters:
    """Test event filter implementations."""
    
    def test_type_filter(self):
        """Test filtering by event type."""
        filter = TypeFilter([StreamStartEvent, StreamDeltaEvent])
        
        # Should pass
        assert filter.should_process(StreamStartEvent())
        assert filter.should_process(StreamDeltaEvent(delta="test"))
        
        # Should not pass
        assert not filter.should_process(StreamCompleteEvent())
        assert not filter.should_process(StreamErrorEvent(error=Exception()))
    
    def test_provider_filter(self):
        """Test filtering by provider."""
        filter = ProviderFilter(["openai", "anthropic"])
        
        # Should pass
        assert filter.should_process(StreamStartEvent(provider="openai"))
        assert filter.should_process(StreamStartEvent(provider="ANTHROPIC"))
        
        # Should not pass
        assert not filter.should_process(StreamStartEvent(provider="xai"))
        assert not filter.should_process(StreamStartEvent())  # No provider
    
    def test_predicate_filter(self):
        """Test filtering with custom predicate."""
        # Filter for events with specific metadata
        def has_priority(event: StreamEvent) -> bool:
            return event.metadata.get("priority") == "high"
        
        filter = PredicateFilter(has_priority)
        
        # Should pass
        event1 = StreamStartEvent()
        event1.metadata["priority"] = "high"
        assert filter.should_process(event1)
        
        # Should not pass
        event2 = StreamStartEvent()
        event2.metadata["priority"] = "low"
        assert not filter.should_process(event2)
        
        # Test error handling
        def failing_predicate(event: StreamEvent) -> bool:
            raise ValueError("Test error")
        
        filter2 = PredicateFilter(failing_predicate)
        assert not filter2.should_process(StreamStartEvent())
    
    def test_composite_filter_and(self):
        """Test composite filter with AND logic."""
        type_filter = TypeFilter([StreamDeltaEvent])
        provider_filter = ProviderFilter(["openai"])
        
        composite = CompositeFilter([type_filter, provider_filter], require_all=True)
        
        # Should pass (both conditions met)
        assert composite.should_process(StreamDeltaEvent(provider="openai"))
        
        # Should not pass (wrong type)
        assert not composite.should_process(StreamStartEvent(provider="openai"))
        
        # Should not pass (wrong provider)
        assert not composite.should_process(StreamDeltaEvent(provider="anthropic"))
    
    def test_composite_filter_or(self):
        """Test composite filter with OR logic."""
        type_filter = TypeFilter([StreamStartEvent])
        provider_filter = ProviderFilter(["openai"])
        
        composite = CompositeFilter([type_filter, provider_filter], require_all=False)
        
        # Should pass (at least one condition met)
        assert composite.should_process(StreamStartEvent(provider="anthropic"))
        assert composite.should_process(StreamDeltaEvent(provider="openai"))
        
        # Should not pass (no conditions met)
        assert not composite.should_process(StreamDeltaEvent(provider="anthropic"))


class TestEventTransformers:
    """Test event transformer implementations."""
    
    @pytest.mark.asyncio
    async def test_correlation_transformer(self):
        """Test correlation ID transformer."""
        # Test with provided ID
        transformer = CorrelationTransformer("test-correlation-123")
        event = StreamStartEvent()
        
        result = await transformer.transform(event)
        assert result is not None
        assert result.metadata["correlation_id"] == "test-correlation-123"
        
        # Test with auto-generated ID
        transformer2 = CorrelationTransformer()
        event2 = StreamDeltaEvent()
        
        result2 = await transformer2.transform(event2)
        assert result2 is not None
        assert "correlation_id" in result2.metadata
        assert len(result2.metadata["correlation_id"]) > 0
    
    @pytest.mark.asyncio
    async def test_timestamp_transformer(self):
        """Test timestamp transformer."""
        transformer = TimestampTransformer()
        event = StreamStartEvent()
        
        before = time.time()
        result = await transformer.transform(event)
        after = time.time()
        
        assert result is not None
        assert "timestamp" in result.metadata
        assert "datetime" in result.metadata
        assert before <= result.metadata["timestamp"] <= after
    
    @pytest.mark.asyncio
    async def test_metrics_transformer(self):
        """Test metrics transformer."""
        transformer = MetricsTransformer()
        
        # Test start event
        start_event = StreamStartEvent()
        result = await transformer.transform(start_event)
        assert "metrics_start" in result.metadata
        
        # Test first delta event
        delta1 = StreamDeltaEvent(delta="First")
        result = await transformer.transform(delta1)
        assert "ttft" in result.metadata
        assert "is_first_token" in result.metadata
        assert result.metadata["is_first_token"] is True
        
        # Test subsequent delta
        delta2 = StreamDeltaEvent(delta="Second")
        result = await transformer.transform(delta2)
        assert "is_first_token" not in result.metadata
        
        # Test complete event
        complete = StreamCompleteEvent()
        result = await transformer.transform(complete)
        assert "total_duration" in result.metadata
        assert "metrics_summary" in result.metadata


class TestEventProcessor:
    """Test event processor functionality."""
    
    @pytest.mark.asyncio
    async def test_basic_processing(self):
        """Test basic event processing."""
        processor = EventProcessor()
        
        # Process events
        event1 = StreamStartEvent()
        result1 = await processor.process_event(event1)
        assert result1 is not None
        assert processor.metrics.events_processed == 1
        
        event2 = StreamDeltaEvent(delta="test")
        result2 = await processor.process_event(event2)
        assert result2 is not None
        assert processor.metrics.events_processed == 2
    
    @pytest.mark.asyncio
    async def test_filtering(self):
        """Test event filtering."""
        processor = EventProcessor()
        processor.add_filter(TypeFilter([StreamStartEvent]))
        
        # Should pass filter
        start = StreamStartEvent()
        result = await processor.process_event(start)
        assert result is not None
        assert processor.metrics.events_processed == 1
        assert processor.metrics.events_filtered == 0
        
        # Should not pass filter
        delta = StreamDeltaEvent()
        result = await processor.process_event(delta)
        assert result is None
        assert processor.metrics.events_processed == 2
        assert processor.metrics.events_filtered == 1
    
    @pytest.mark.asyncio
    async def test_transformation(self):
        """Test event transformation."""
        processor = EventProcessor()
        processor.add_transformer(CorrelationTransformer("test-123"))
        processor.add_transformer(TimestampTransformer())
        
        event = StreamStartEvent()
        result = await processor.process_event(event)
        
        assert result is not None
        assert result.metadata["correlation_id"] == "test-123"
        assert "timestamp" in result.metadata
        assert processor.metrics.events_transformed == 2
    
    @pytest.mark.asyncio
    async def test_background_processing(self):
        """Test background event processing."""
        processor = EventProcessor(background=True)
        await processor.start()
        
        # Submit events
        events = [
            StreamStartEvent(),
            StreamDeltaEvent(delta="test1"),
            StreamDeltaEvent(delta="test2"),
            StreamCompleteEvent()
        ]
        
        for event in events:
            await processor.submit_event(event)
        
        # Give time for background processing
        await asyncio.sleep(0.1)
        
        assert processor.metrics.events_processed == 4
        
        await processor.stop()
    
    @pytest.mark.asyncio
    async def test_stream_processing(self):
        """Test processing an event stream."""
        processor = EventProcessor()
        processor.add_filter(TypeFilter([StreamStartEvent, StreamDeltaEvent]))
        processor.add_transformer(CorrelationTransformer())
        
        async def event_stream():
            yield StreamStartEvent()
            yield StreamDeltaEvent(delta="test1")
            yield StreamCompleteEvent()  # Should be filtered
            yield StreamDeltaEvent(delta="test2")
        
        results = []
        async for event in processor.process_stream(event_stream()):
            results.append(event)
        
        assert len(results) == 3
        assert isinstance(results[0], StreamStartEvent)
        assert isinstance(results[1], StreamDeltaEvent)
        assert isinstance(results[2], StreamDeltaEvent)
        
        # All should have correlation ID
        correlation_id = results[0].metadata["correlation_id"]
        assert all(e.metadata["correlation_id"] == correlation_id for e in results)
    
    def test_metrics(self):
        """Test processor metrics."""
        processor = EventProcessor()
        metrics = processor.metrics
        
        assert isinstance(metrics, ProcessorMetrics)
        assert metrics.events_processed == 0
        assert metrics.events_per_second == 0
        assert metrics.average_processing_time_ms == 0


class TestBatchedEventProcessor:
    """Test batched event processor functionality."""
    
    @pytest.mark.asyncio
    async def test_batching(self):
        """Test event batching."""
        batches_received = []
        
        def batch_handler(batch: List[StreamEvent]):
            batches_received.append(batch)
        
        processor = BatchedEventProcessor(
            batch_size=3,
            batch_timeout_ms=100,
            batch_handler=batch_handler
        )
        
        # Process events that will trigger batch by size
        events = [
            StreamStartEvent(),
            StreamDeltaEvent(delta="1"),
            StreamDeltaEvent(delta="2")
        ]
        
        for event in events:
            await processor.process_event(event)
        
        # Should have one batch
        assert len(batches_received) == 1
        assert len(batches_received[0]) == 3
    
    @pytest.mark.asyncio
    async def test_batch_timeout(self):
        """Test batch timeout."""
        batches_received = []
        
        def batch_handler(batch: List[StreamEvent]):
            batches_received.append(batch)
        
        processor = BatchedEventProcessor(
            batch_size=10,
            batch_timeout_ms=50,
            batch_handler=batch_handler
        )
        
        # Process fewer events than batch size
        await processor.process_event(StreamStartEvent())
        await processor.process_event(StreamDeltaEvent())
        
        # Wait for timeout
        await asyncio.sleep(0.1)
        
        # Should have one batch from timeout
        assert len(batches_received) == 1
        assert len(batches_received[0]) == 2
    
    @pytest.mark.asyncio
    async def test_async_batch_handler(self):
        """Test async batch handler."""
        batches_received = []
        
        async def async_batch_handler(batch: List[StreamEvent]):
            await asyncio.sleep(0.01)  # Simulate async work
            batches_received.append(batch)
        
        processor = BatchedEventProcessor(
            batch_size=2,
            batch_handler=async_batch_handler
        )
        
        await processor.process_event(StreamStartEvent())
        await processor.process_event(StreamDeltaEvent())
        
        await asyncio.sleep(0.05)  # Wait for async handler
        
        assert len(batches_received) == 1
        assert len(batches_received[0]) == 2
    
    @pytest.mark.asyncio
    async def test_flush(self):
        """Test flushing pending events."""
        batches_received = []
        
        def batch_handler(batch: List[StreamEvent]):
            batches_received.append(batch)
        
        processor = BatchedEventProcessor(
            batch_size=10,
            batch_timeout_ms=1000,
            batch_handler=batch_handler
        )
        
        # Add events but don't fill batch
        await processor.process_event(StreamStartEvent())
        await processor.process_event(StreamDeltaEvent())
        
        # Flush should process pending events
        await processor.flush()
        
        assert len(batches_received) == 1
        assert len(batches_received[0]) == 2


class TestFactoryFunction:
    """Test create_event_processor factory function."""
    
    def test_create_basic_processor(self):
        """Test creating basic processor."""
        processor = create_event_processor()
        
        assert isinstance(processor, EventProcessor)
        assert len(processor.filters) == 0
        assert len(processor.transformers) == 2  # correlation + timestamp by default
    
    def test_create_filtered_processor(self):
        """Test creating processor with filters."""
        processor = create_event_processor(
            event_types=[StreamStartEvent, StreamDeltaEvent],
            providers=["openai"],
            predicate=lambda e: e.metadata.get("priority") == "high"
        )
        
        assert len(processor.filters) == 3
        assert any(isinstance(f, TypeFilter) for f in processor.filters)
        assert any(isinstance(f, ProviderFilter) for f in processor.filters)
        assert any(isinstance(f, PredicateFilter) for f in processor.filters)
    
    def test_create_processor_with_transformers(self):
        """Test creating processor with transformers."""
        processor = create_event_processor(
            add_correlation=True,
            add_timestamp=True,
            add_metrics=True
        )
        
        assert len(processor.transformers) == 3
        transformer_types = [type(t) for t in processor.transformers]
        assert CorrelationTransformer in transformer_types
        assert TimestampTransformer in transformer_types
        assert MetricsTransformer in transformer_types
    
    def test_create_batched_processor(self):
        """Test creating batched processor."""
        handler = MagicMock()
        
        processor = create_event_processor(
            batch_size=100,
            batch_timeout_ms=500,
            batch_handler=handler
        )
        
        assert isinstance(processor, BatchedEventProcessor)
        assert processor.batch_size == 100
        assert processor.batch_timeout_ms == 500
        assert processor.batch_handler == handler
    
    def test_create_background_processor(self):
        """Test creating background processor."""
        processor = create_event_processor(background=True)
        
        assert processor.background is True
        assert processor._event_queue is not None