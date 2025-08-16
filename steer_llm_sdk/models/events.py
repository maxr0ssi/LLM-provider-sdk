"""Event models for streaming responses.

This module defines the event types used throughout the streaming pipeline.
"""

from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field
import time


@dataclass
class StreamEvent:
    """Base class for all streaming events."""
    type: str = ""  # Will be set by subclasses
    provider: Optional[str] = None
    model: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamStartEvent(StreamEvent):
    """Event emitted when streaming starts."""
    type: str = field(default="start", init=False)
    stream_id: Optional[str] = None
    
    def __post_init__(self):
        self.type = "start"


@dataclass
class StreamDeltaEvent(StreamEvent):
    """Event emitted for each stream delta/chunk."""
    type: str = field(default="delta", init=False)
    delta: Optional[Union[str, Dict[str, Any]]] = None
    chunk_index: int = 0
    is_json: bool = False
    
    def __post_init__(self):
        self.type = "delta"
    
    def get_text(self) -> str:
        """Extract text content from delta."""
        if isinstance(self.delta, str):
            return self.delta
        elif isinstance(self.delta, dict):
            # Try common keys
            for key in ['text', 'content', 'chunk', 'delta']:
                if key in self.delta:
                    value = self.delta[key]
                    if isinstance(value, str):
                        return value
        return ""


@dataclass
class StreamUsageEvent(StreamEvent):
    """Event emitted when usage data is available."""
    type: str = field(default="usage", init=False)
    usage: Dict[str, Any] = field(default_factory=dict)
    is_estimated: bool = False
    confidence: float = 1.0
    
    def __post_init__(self):
        self.type = "usage"


@dataclass
class StreamCompleteEvent(StreamEvent):
    """Event emitted when streaming completes successfully."""
    type: str = field(default="complete", init=False)
    total_chunks: int = 0
    duration_ms: float = 0.0
    final_usage: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        self.type = "complete"


@dataclass
class StreamErrorEvent(StreamEvent):
    """Event emitted when an error occurs during streaming."""
    error: Optional[Exception] = None
    type: str = field(default="error", init=False)
    error_type: str = ""
    is_retryable: bool = False
    
    def __post_init__(self):
        self.type = "error"
        if not self.error_type and self.error:
            self.error_type = type(self.error).__name__