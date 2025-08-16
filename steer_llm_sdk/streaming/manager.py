from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Union
import time

from .types import StreamDelta
from ..models.events import (
    StreamEvent,
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)


class EventManager:
    """Event manager for streaming events with support for both typed and untyped callbacks."""
    
    def __init__(
        self,
        # Support both legacy (Any) and typed callbacks
        on_start: Optional[Union[
            Callable[[Any], Awaitable[None]],
            Callable[[StreamStartEvent], Awaitable[None]]
        ]] = None,
        on_delta: Optional[Union[
            Callable[[Any], Awaitable[None]],
            Callable[[StreamDeltaEvent], Awaitable[None]]
        ]] = None,
        on_usage: Optional[Union[
            Callable[[Any], Awaitable[None]],
            Callable[[StreamUsageEvent], Awaitable[None]]
        ]] = None,
        on_complete: Optional[Union[
            Callable[[Any], Awaitable[None]],
            Callable[[StreamCompleteEvent], Awaitable[None]]
        ]] = None,
        on_error: Optional[Union[
            Callable[[Exception], Awaitable[None]],
            Callable[[StreamErrorEvent], Awaitable[None]]
        ]] = None,
        # Global metadata for event enrichment
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        sdk_version: Optional[str] = None,
        on_create_event: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        metrics_enabled: bool = False,
    ) -> None:
        self.on_start = on_start
        self.on_delta = on_delta
        self.on_usage = on_usage
        self.on_complete = on_complete
        self.on_error = on_error
        
        # Metadata enrichment
        self.request_id = request_id
        self.trace_id = trace_id
        self.sdk_version = sdk_version or self._get_sdk_version()
        self.on_create_event = on_create_event
        self.metrics_enabled = metrics_enabled
    
    def _get_sdk_version(self) -> str:
        """Get SDK version from package."""
        try:
            from .. import __version__
            return __version__
        except ImportError:
            return "unknown"
    
    def _enrich_kwargs(self, event_type: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich kwargs with global metadata."""
        # Add request_id if not already present (it's a field in StreamEvent)
        if self.request_id and 'request_id' not in kwargs:
            kwargs['request_id'] = self.request_id
        
        # Ensure timestamp
        kwargs.setdefault('timestamp', time.time())
        
        # Add SDK version and trace_id to metadata
        metadata = kwargs.setdefault('metadata', {})
        metadata['sdk_version'] = self.sdk_version
        if self.trace_id and 'trace_id' not in metadata:
            metadata['trace_id'] = self.trace_id
        
        # Apply custom enrichment hook
        if self.on_create_event:
            kwargs = self.on_create_event(event_type, kwargs)
        
        # Optional metrics
        if self.metrics_enabled:
            self._increment_metric('events.created', tags={'type': event_type})
        
        return kwargs
    
    def _increment_metric(self, metric: str, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a metric (no-op for now, hook for future metrics integration)."""
        # Future: integrate with observability layer
        pass

    async def emit_start(self, event: Union[Any, StreamStartEvent]) -> None:
        """Emit start event."""
        if self.on_start:
            await self.on_start(event)

    async def emit_delta(self, event: Union[Any, StreamDeltaEvent]) -> None:
        """Emit delta event."""
        if self.on_delta:
            await self.on_delta(event)

    async def emit_usage(self, event: Union[Any, StreamUsageEvent]) -> None:
        """Emit usage event."""
        if self.on_usage:
            await self.on_usage(event)

    async def emit_complete(self, event: Union[Any, StreamCompleteEvent]) -> None:
        """Emit complete event."""
        if self.on_complete:
            await self.on_complete(event)

    async def emit_error(self, event: Union[Exception, StreamErrorEvent]) -> None:
        """Emit error event."""
        if self.on_error:
            await self.on_error(event)
    
    async def emit_event(self, event: StreamEvent) -> None:
        """Emit a typed event to the appropriate handler.
        
        Args:
            event: The typed event to emit
        """
        if isinstance(event, StreamStartEvent):
            await self.emit_start(event)
        elif isinstance(event, StreamDeltaEvent):
            await self.emit_delta(event)
        elif isinstance(event, StreamUsageEvent):
            await self.emit_usage(event)
        elif isinstance(event, StreamCompleteEvent):
            await self.emit_complete(event)
        elif isinstance(event, StreamErrorEvent):
            await self.emit_error(event)
    
    # Factory methods for creating events with consistent metadata
    def create_start_event(self, provider: str, model: str, **kwargs) -> StreamStartEvent:
        """Create a start event with consistent metadata."""
        kwargs = self._enrich_kwargs('start', kwargs)
        from ..models.events import StreamStartEvent
        return StreamStartEvent(provider=provider, model=model, **kwargs)
    
    def create_delta_event(self, delta: Any, chunk_index: int, **kwargs) -> StreamDeltaEvent:
        """Create a delta event with consistent metadata."""
        kwargs = self._enrich_kwargs('delta', kwargs)
        from ..models.events import StreamDeltaEvent
        return StreamDeltaEvent(delta=delta, chunk_index=chunk_index, **kwargs)
    
    def create_usage_event(self, usage: Dict[str, Any], is_estimated: bool = False, **kwargs) -> StreamUsageEvent:
        """Create a usage event with consistent metadata."""
        kwargs = self._enrich_kwargs('usage', kwargs)
        from ..models.events import StreamUsageEvent
        return StreamUsageEvent(usage=usage, is_estimated=is_estimated, **kwargs)
    
    def create_complete_event(self, total_chunks: int, duration_ms: float, **kwargs) -> StreamCompleteEvent:
        """Create a complete event with consistent metadata."""
        kwargs = self._enrich_kwargs('complete', kwargs)
        from ..models.events import StreamCompleteEvent
        return StreamCompleteEvent(total_chunks=total_chunks, duration_ms=duration_ms, **kwargs)
    
    def create_error_event(self, error: Exception, error_type: str, **kwargs) -> StreamErrorEvent:
        """Create an error event with consistent metadata."""
        kwargs = self._enrich_kwargs('error', kwargs)
        from ..models.events import StreamErrorEvent
        return StreamErrorEvent(error=error, error_type=error_type, **kwargs)


