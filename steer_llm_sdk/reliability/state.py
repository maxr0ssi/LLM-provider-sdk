"""
Stream state management for reliability.

This module manages streaming state to enable recovery
and partial response preservation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time
import hashlib
import json


@dataclass
class ChunkMetadata:
    """Metadata for a stream chunk."""
    index: int
    timestamp: float
    size: int
    hash: str
    content_type: str = "text"  # text, json, binary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "size": self.size,
            "hash": self.hash,
            "content_type": self.content_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChunkMetadata':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class StreamState:
    """
    Manages state for streaming operations.
    
    Tracks chunks, metadata, and checkpoints to enable
    stream recovery and partial response handling.
    """
    request_id: str
    provider: str = ""
    model: str = ""
    start_time: float = field(default_factory=time.time)
    chunks: List[ChunkMetadata] = field(default_factory=list)
    partial_response: List[str] = field(default_factory=list)
    total_tokens: int = 0
    last_checkpoint: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None
    
    def record_chunk(self, chunk: str, index: Optional[int] = None):
        """
        Record a chunk with metadata.
        
        Args:
            chunk: The chunk content
            index: Optional explicit index (auto-increments if not provided)
        """
        if index is None:
            index = len(self.chunks)
        
        # Detect content type
        content_type = self._detect_content_type(chunk)
        
        # Create metadata
        metadata = ChunkMetadata(
            index=index,
            timestamp=time.time(),
            size=len(chunk),
            hash=hashlib.md5(chunk.encode()).hexdigest(),
            content_type=content_type
        )
        
        self.chunks.append(metadata)
        self.partial_response.append(chunk)
        self.total_tokens += self._estimate_tokens(chunk)
    
    def _detect_content_type(self, chunk: str) -> str:
        """Detect the content type of a chunk."""
        # Try to parse as JSON
        try:
            json.loads(chunk)
            return "json"
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Check if it looks like binary data
        try:
            chunk.encode('utf-8')
            return "text"
        except UnicodeEncodeError:
            return "binary"
    
    def can_resume(self) -> bool:
        """Check if stream can be resumed from current state."""
        return len(self.chunks) > 0
    
    def get_resume_position(self) -> int:
        """Get position to resume streaming from."""
        if self.last_checkpoint is not None:
            return self.last_checkpoint
        return len(self.chunks)
    
    def create_checkpoint(self):
        """Create a checkpoint for current state."""
        self.last_checkpoint = len(self.chunks)
        self.metadata['checkpoint_time'] = time.time()
        self.metadata['checkpoint_tokens'] = self.total_tokens
    
    def get_partial_response(self) -> str:
        """Get concatenated partial response."""
        return ''.join(self.partial_response)
    
    def get_json_chunks(self) -> List[Dict[str, Any]]:
        """Get all JSON chunks parsed."""
        json_chunks = []
        for i, chunk_metadata in enumerate(self.chunks):
            if chunk_metadata.content_type == "json" and i < len(self.partial_response):
                try:
                    parsed = json.loads(self.partial_response[i])
                    json_chunks.append(parsed)
                except json.JSONDecodeError:
                    pass
        return json_chunks
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        # Simple estimation: ~4 chars per token
        # This could be replaced with tiktoken for accuracy
        return len(text) // 4
    
    def record_error(self, error: str):
        """Record an error occurrence."""
        self.error_count += 1
        self.last_error = error
        self.last_error_time = time.time()
    
    def get_duration(self) -> float:
        """Get total duration since start."""
        return time.time() - self.start_time
    
    def get_chunks_per_second(self) -> float:
        """Calculate chunks per second rate."""
        duration = self.get_duration()
        if duration > 0:
            return len(self.chunks) / duration
        return 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of stream state."""
        return {
            "request_id": self.request_id,
            "provider": self.provider,
            "model": self.model,
            "chunks_received": len(self.chunks),
            "total_bytes": sum(c.size for c in self.chunks),
            "total_tokens": self.total_tokens,
            "duration": self.get_duration(),
            "chunks_per_second": self.get_chunks_per_second(),
            "has_checkpoint": self.last_checkpoint is not None,
            "error_count": self.error_count,
            "last_error": self.last_error
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "provider": self.provider,
            "model": self.model,
            "start_time": self.start_time,
            "chunks": [c.to_dict() for c in self.chunks],
            "partial_response": self.partial_response,
            "total_tokens": self.total_tokens,
            "last_checkpoint": self.last_checkpoint,
            "metadata": self.metadata,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreamState':
        """Create StreamState from dictionary."""
        # Convert chunk metadata
        chunks = [ChunkMetadata.from_dict(c) for c in data.get("chunks", [])]
        
        # Create state
        state = cls(
            request_id=data["request_id"],
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            start_time=data.get("start_time", time.time())
        )
        
        # Restore data
        state.chunks = chunks
        state.partial_response = data.get("partial_response", [])
        state.total_tokens = data.get("total_tokens", 0)
        state.last_checkpoint = data.get("last_checkpoint")
        state.metadata = data.get("metadata", {})
        state.error_count = data.get("error_count", 0)
        state.last_error = data.get("last_error")
        state.last_error_time = data.get("last_error_time")
        
        return state


class StreamStateManager:
    """Manages multiple stream states."""
    
    def __init__(self):
        self.states: Dict[str, StreamState] = {}
    
    def create_state(
        self,
        request_id: str,
        provider: str = "",
        model: str = ""
    ) -> StreamState:
        """Create and track a new stream state."""
        state = StreamState(
            request_id=request_id,
            provider=provider,
            model=model
        )
        self.states[request_id] = state
        return state
    
    def get_state(self, request_id: str) -> Optional[StreamState]:
        """Get stream state by request ID."""
        return self.states.get(request_id)
    
    def remove_state(self, request_id: str) -> Optional[StreamState]:
        """Remove and return stream state."""
        return self.states.pop(request_id, None)
    
    def get_active_streams(self) -> List[StreamState]:
        """Get all active stream states."""
        return list(self.states.values())
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all stream states."""
        return {
            "active_streams": len(self.states),
            "total_chunks": sum(len(s.chunks) for s in self.states.values()),
            "total_tokens": sum(s.total_tokens for s in self.states.values()),
            "streams": {
                request_id: state.get_summary()
                for request_id, state in self.states.items()
            }
        }
    
    def cleanup_old_states(self, max_age_seconds: float = 3600):
        """Remove states older than max age."""
        current_time = time.time()
        to_remove = []
        
        for request_id, state in self.states.items():
            if current_time - state.start_time > max_age_seconds:
                to_remove.append(request_id)
        
        for request_id in to_remove:
            self.remove_state(request_id)