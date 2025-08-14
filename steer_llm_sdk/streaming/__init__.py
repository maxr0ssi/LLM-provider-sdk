"""Streaming and events layer for real-time LLM responses.

This layer handles:
- Stream delta normalization across providers
- Event management (on_start, on_delta, on_usage, on_finish)
- Streaming response types and interfaces
- Usage data aggregation during streaming
"""

from .adapter import StreamAdapter
from .helpers import StreamingHelper
from .manager import (
    EventManager,
    StreamStartEvent,
    StreamDeltaEvent, 
    StreamUsageEvent,
    StreamCompleteEvent
)
from .types import StreamDelta, DeltaType

__all__ = [
    "StreamAdapter",
    "StreamingHelper",
    "EventManager", 
    "StreamDelta",
    "DeltaType",
    "StreamStartEvent",
    "StreamDeltaEvent",
    "StreamUsageEvent", 
    "StreamCompleteEvent"
]


