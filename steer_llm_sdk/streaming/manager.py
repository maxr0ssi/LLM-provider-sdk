from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Union

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
    ) -> None:
        self.on_start = on_start
        self.on_delta = on_delta
        self.on_usage = on_usage
        self.on_complete = on_complete
        self.on_error = on_error

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


