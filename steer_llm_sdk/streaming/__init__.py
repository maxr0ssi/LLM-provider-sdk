"""Streaming and events layer for real-time LLM responses.

This layer handles:
- Stream delta normalization across providers
- Event management (on_start, on_delta, on_usage, on_finish)
- Streaming response types and interfaces
- Usage data aggregation during streaming
"""

from .adapter import StreamAdapter
from .manager import EventManager
from .types import StreamDelta, DeltaType

__all__ = [
    "StreamAdapter",
    "EventManager", 
    "StreamDelta",
    "DeltaType"
]


