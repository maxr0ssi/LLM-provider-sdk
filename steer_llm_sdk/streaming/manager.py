from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from .types import StreamDelta


class EventManager:
    def __init__(
        self,
        on_start: Optional[Callable[[Any], Awaitable[None]]] = None,
        on_delta: Optional[Callable[[Any], Awaitable[None]]] = None,
        on_usage: Optional[Callable[[Any], Awaitable[None]]] = None,
        on_complete: Optional[Callable[[Any], Awaitable[None]]] = None,
        on_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
    ) -> None:
        self.on_start = on_start
        self.on_delta = on_delta
        self.on_usage = on_usage
        self.on_complete = on_complete
        self.on_error = on_error

    async def emit_start(self, meta: Any) -> None:
        if self.on_start:
            await self.on_start(meta)

    async def emit_delta(self, delta: Any) -> None:
        if self.on_delta:
            await self.on_delta(delta)

    async def emit_usage(self, usage: Any) -> None:
        if self.on_usage:
            await self.on_usage(usage)

    async def emit_complete(self, result: Any) -> None:
        if self.on_complete:
            await self.on_complete(result)

    async def emit_error(self, error: Exception) -> None:
        if self.on_error:
            await self.on_error(error)


# Typed Event Classes for structured event data

@dataclass
class StreamStartEvent:
    """Event emitted when streaming starts."""
    provider: str
    model: str
    request_id: str


@dataclass
class StreamDeltaEvent:
    """Event emitted for each streaming delta."""
    delta: StreamDelta
    chunk_index: int


@dataclass
class StreamUsageEvent:
    """Event emitted when usage data is available."""
    usage: Dict[str, Any]
    provider: str
    model: str


@dataclass
class StreamCompleteEvent:
    """Event emitted when streaming completes."""
    total_chunks: int
    duration_seconds: float
    final_text: str
    provider: str
    model: str

