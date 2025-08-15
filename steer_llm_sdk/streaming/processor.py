"""
Event processing pipeline for streaming responses.

This module provides event filtering, transformation, and batching
capabilities for streaming events across all providers.
"""

from typing import List, Callable, Any, Optional, AsyncGenerator, Dict, Union, TypeVar
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import asyncio
import time
import logging
from collections import deque
from datetime import datetime, timezone
import uuid

from ..models.events import (
    StreamEvent,
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=StreamEvent)


class EventFilter(ABC):
    """Base class for event filters."""
    
    @abstractmethod
    def should_process(self, event: StreamEvent) -> bool:
        """Determine if an event should be processed.
        
        Args:
            event: The event to check
            
        Returns:
            True if the event should be processed, False otherwise
        """
        pass


class TypeFilter(EventFilter):
    """Filter events by type."""
    
    def __init__(self, allowed_types: List[type]):
        """Initialize the type filter.
        
        Args:
            allowed_types: List of event types to allow
        """
        self.allowed_types = set(allowed_types)
    
    def should_process(self, event: StreamEvent) -> bool:
        return type(event) in self.allowed_types


class ProviderFilter(EventFilter):
    """Filter events by provider."""
    
    def __init__(self, allowed_providers: List[str]):
        """Initialize the provider filter.
        
        Args:
            allowed_providers: List of provider names to allow
        """
        self.allowed_providers = set(p.lower() for p in allowed_providers)
    
    def should_process(self, event: StreamEvent) -> bool:
        provider = getattr(event, 'provider', None)
        return provider and provider.lower() in self.allowed_providers


class PredicateFilter(EventFilter):
    """Filter events using a custom predicate."""
    
    def __init__(self, predicate: Callable[[StreamEvent], bool]):
        """Initialize the predicate filter.
        
        Args:
            predicate: Function that returns True for events to process
        """
        self.predicate = predicate
    
    def should_process(self, event: StreamEvent) -> bool:
        try:
            return self.predicate(event)
        except Exception as e:
            logger.warning(f"Predicate filter error: {e}")
            return False


class CompositeFilter(EventFilter):
    """Combine multiple filters with AND/OR logic."""
    
    def __init__(self, filters: List[EventFilter], require_all: bool = True):
        """Initialize the composite filter.
        
        Args:
            filters: List of filters to combine
            require_all: If True, all filters must pass (AND). If False, any filter can pass (OR).
        """
        self.filters = filters
        self.require_all = require_all
    
    def should_process(self, event: StreamEvent) -> bool:
        if self.require_all:
            return all(f.should_process(event) for f in self.filters)
        else:
            return any(f.should_process(event) for f in self.filters)


class EventTransformer(ABC):
    """Base class for event transformers."""
    
    @abstractmethod
    async def transform(self, event: StreamEvent) -> Optional[StreamEvent]:
        """Transform an event.
        
        Args:
            event: The event to transform
            
        Returns:
            Transformed event or None to filter out
        """
        pass


class CorrelationTransformer(EventTransformer):
    """Add correlation IDs to events."""
    
    def __init__(self, correlation_id: Optional[str] = None):
        """Initialize the correlation transformer.
        
        Args:
            correlation_id: Correlation ID to use (auto-generated if not provided)
        """
        self.correlation_id = correlation_id or str(uuid.uuid4())
    
    async def transform(self, event: StreamEvent) -> Optional[StreamEvent]:
        """Add correlation ID to event metadata."""
        event.metadata['correlation_id'] = self.correlation_id
        return event


class TimestampTransformer(EventTransformer):
    """Add high-precision timestamps to events."""
    
    async def transform(self, event: StreamEvent) -> Optional[StreamEvent]:
        """Add timestamp to event metadata."""
        event.metadata['timestamp'] = time.time()
        event.metadata['datetime'] = datetime.now(timezone.utc).isoformat()
        return event


class MetricsTransformer(EventTransformer):
    """Extract and track metrics from events."""
    
    def __init__(self):
        """Initialize metrics transformer."""
        self.metrics = {
            'first_token_time': None,
            'last_token_time': None,
            'token_count': 0,
            'total_chunks': 0,
            'errors': 0
        }
        self.start_time = time.time()
    
    async def transform(self, event: StreamEvent) -> Optional[StreamEvent]:
        """Extract metrics from event."""
        current_time = time.time()
        
        if isinstance(event, StreamStartEvent):
            self.start_time = current_time
            event.metadata['metrics_start'] = current_time
            
        elif isinstance(event, StreamDeltaEvent):
            self.metrics['total_chunks'] += 1
            if self.metrics['first_token_time'] is None:
                self.metrics['first_token_time'] = current_time
                event.metadata['ttft'] = current_time - self.start_time
                event.metadata['is_first_token'] = True
            self.metrics['last_token_time'] = current_time
            
        elif isinstance(event, StreamCompleteEvent):
            event.metadata['total_duration'] = current_time - self.start_time
            event.metadata['metrics_summary'] = self.metrics.copy()
            
        elif isinstance(event, StreamErrorEvent):
            self.metrics['errors'] += 1
            
        return event


@dataclass
class ProcessorMetrics:
    """Metrics for event processor performance."""
    events_processed: int = 0
    events_filtered: int = 0
    events_transformed: int = 0
    events_batched: int = 0
    processing_time_ms: float = 0.0
    last_event_time: Optional[float] = None
    start_time: float = field(default_factory=time.time)
    
    @property
    def events_per_second(self) -> float:
        """Calculate events processed per second."""
        elapsed = time.time() - self.start_time
        return self.events_processed / elapsed if elapsed > 0 else 0
    
    @property
    def average_processing_time_ms(self) -> float:
        """Calculate average processing time per event."""
        if self.events_processed == 0:
            return 0.0
        return self.processing_time_ms / self.events_processed


class EventProcessor:
    """Base event processor with filtering and transformation."""
    
    def __init__(
        self,
        filters: Optional[List[EventFilter]] = None,
        transformers: Optional[List[EventTransformer]] = None,
        background: bool = False
    ):
        """Initialize the event processor.
        
        Args:
            filters: List of filters to apply
            transformers: List of transformers to apply
            background: If True, process events in background
        """
        self.filters = filters or []
        self.transformers = transformers or []
        self.background = background
        self.metrics = ProcessorMetrics()
        self._background_task: Optional[asyncio.Task] = None
        self._event_queue: Optional[asyncio.Queue] = None
        
        if background:
            self._event_queue = asyncio.Queue()
    
    def add_filter(self, filter: EventFilter) -> None:
        """Add a filter to the processor."""
        self.filters.append(filter)
    
    def add_transformer(self, transformer: EventTransformer) -> None:
        """Add a transformer to the processor."""
        self.transformers.append(transformer)
    
    def should_process(self, event: StreamEvent) -> bool:
        """Check if an event should be processed."""
        if not self.filters:
            return True
        
        for filter in self.filters:
            if not filter.should_process(event):
                self.metrics.events_filtered += 1
                return False
        
        return True
    
    async def transform_event(self, event: StreamEvent) -> Optional[StreamEvent]:
        """Apply all transformers to an event."""
        current_event = event
        
        for transformer in self.transformers:
            current_event = await transformer.transform(current_event)
            if current_event is None:
                self.metrics.events_filtered += 1
                return None
            self.metrics.events_transformed += 1
        
        return current_event
    
    async def process_event(self, event: StreamEvent) -> Optional[StreamEvent]:
        """Process a single event through the pipeline.
        
        Args:
            event: The event to process
            
        Returns:
            Processed event or None if filtered out
        """
        start_time = time.time()
        
        try:
            # Update processed count (attempt to process)
            self.metrics.events_processed += 1
            
            # Check filters
            if not self.should_process(event):
                return None
            
            # Apply transformers
            transformed = await self.transform_event(event)
            if transformed is None:
                return None
            
            # Update metrics
            self.metrics.last_event_time = time.time()
            self.metrics.processing_time_ms += (time.time() - start_time) * 1000
            
            return transformed
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return None
    
    async def submit_event(self, event: StreamEvent) -> None:
        """Submit an event for processing.
        
        For background processors, this queues the event.
        For foreground processors, this processes immediately.
        """
        if self.background and self._event_queue:
            await self._event_queue.put(event)
        else:
            await self.process_event(event)
    
    async def start(self) -> None:
        """Start background processing if enabled."""
        if self.background and not self._background_task:
            self._background_task = asyncio.create_task(self._process_background())
    
    async def stop(self) -> None:
        """Stop background processing."""
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None
    
    async def _process_background(self) -> None:
        """Process events from the queue in the background."""
        while True:
            try:
                event = await self._event_queue.get()
                await self.process_event(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background processing error: {e}")
    
    async def process_stream(
        self,
        stream: AsyncGenerator[StreamEvent, None]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Process event stream through pipeline.
        
        Args:
            stream: Async generator of events
            
        Yields:
            Processed events (filtered events are skipped)
        """
        async for event in stream:
            processed = await self.process_event(event)
            if processed is not None:
                yield processed


class BatchedEventProcessor(EventProcessor):
    """Event processor that batches events for efficient processing."""
    
    def __init__(
        self,
        batch_size: int = 100,
        batch_timeout_ms: int = 1000,
        batch_handler: Optional[Callable[[List[StreamEvent]], Any]] = None,
        **kwargs
    ):
        """Initialize the batched event processor.
        
        Args:
            batch_size: Maximum events per batch
            batch_timeout_ms: Maximum time to wait for a batch
            batch_handler: Function to handle batches
            **kwargs: Additional arguments for EventProcessor
        """
        super().__init__(**kwargs)
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.batch_handler = batch_handler
        self._batch: List[StreamEvent] = []
        self._batch_lock = asyncio.Lock()
        self._batch_timer: Optional[asyncio.Task] = None
    
    async def process_event(self, event: StreamEvent) -> Optional[StreamEvent]:
        """Process event and add to batch."""
        processed = await super().process_event(event)
        if processed is None:
            return None
        
        async with self._batch_lock:
            self._batch.append(processed)
            self.metrics.events_batched += 1
            
            # Start timer if this is the first event in batch
            if len(self._batch) == 1:
                self._batch_timer = asyncio.create_task(self._batch_timeout())
            
            # Process batch if full
            if len(self._batch) >= self.batch_size:
                await self._process_batch()
        
        return processed
    
    async def _batch_timeout(self) -> None:
        """Process batch after timeout."""
        await asyncio.sleep(self.batch_timeout_ms / 1000.0)
        async with self._batch_lock:
            if self._batch:
                await self._process_batch()
    
    async def _process_batch(self) -> None:
        """Process the current batch."""
        if not self._batch:
            return
        
        # Cancel timer if active
        if self._batch_timer:
            self._batch_timer.cancel()
            self._batch_timer = None
        
        # Process batch
        batch = self._batch
        self._batch = []
        
        if self.batch_handler:
            try:
                if asyncio.iscoroutinefunction(self.batch_handler):
                    await self.batch_handler(batch)
                else:
                    self.batch_handler(batch)
            except Exception as e:
                logger.error(f"Batch handler error: {e}")
    
    async def flush(self) -> None:
        """Flush any pending batched events."""
        async with self._batch_lock:
            await self._process_batch()
    
    async def stop(self) -> None:
        """Stop processing and flush remaining events."""
        await self.flush()
        await super().stop()


def create_event_processor(
    event_types: Optional[List[type]] = None,
    providers: Optional[List[str]] = None,
    predicate: Optional[Callable[[StreamEvent], bool]] = None,
    add_correlation: bool = True,
    add_timestamp: bool = True,
    add_metrics: bool = False,
    background: bool = False,
    batch_size: Optional[int] = None,
    batch_timeout_ms: int = 1000,
    batch_handler: Optional[Callable[[List[StreamEvent]], Any]] = None
) -> Union[EventProcessor, BatchedEventProcessor]:
    """Create an event processor with common configuration.
    
    Args:
        event_types: Event types to process (None for all)
        providers: Provider names to process (None for all)
        predicate: Custom filter predicate
        add_correlation: Add correlation IDs to events
        add_timestamp: Add timestamps to events
        add_metrics: Add metrics transformer
        background: Process events in background
        batch_size: Batch size (creates BatchedEventProcessor if set)
        batch_timeout_ms: Batch timeout in milliseconds
        batch_handler: Handler for batched events
        
    Returns:
        Configured event processor
    """
    filters = []
    
    if event_types:
        filters.append(TypeFilter(event_types))
    
    if providers:
        filters.append(ProviderFilter(providers))
    
    if predicate:
        filters.append(PredicateFilter(predicate))
    
    transformers = []
    
    if add_correlation:
        transformers.append(CorrelationTransformer())
    
    if add_timestamp:
        transformers.append(TimestampTransformer())
    
    if add_metrics:
        transformers.append(MetricsTransformer())
    
    # Create appropriate processor type
    if batch_size:
        return BatchedEventProcessor(
            filters=filters,
            transformers=transformers,
            background=background,
            batch_size=batch_size,
            batch_timeout_ms=batch_timeout_ms,
            batch_handler=batch_handler
        )
    else:
        return EventProcessor(
            filters=filters,
            transformers=transformers,
            background=background
        )