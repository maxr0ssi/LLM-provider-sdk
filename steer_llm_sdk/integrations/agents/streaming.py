"""Streaming event bridge for agent runtime integrations.

This module provides utilities for bridging provider-specific
streaming events to our normalized EventManager.
"""

import time
from typing import Any, Dict, Optional, Callable, Union
import json

from ...streaming.manager import EventManager
from ...streaming.adapter import StreamAdapter
from ...streaming.types import StreamDelta, DeltaType
from ...models.events import (
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)
from ...streaming.json_handler import JsonStreamHandler
from ...streaming.aggregator import UsageAggregator


class AgentStreamingBridge:
    """Bridge between agent runtime streaming and our EventManager.
    
    This class handles event translation, JSON processing, and usage
    aggregation for agent runtime streaming.
    """
    
    def __init__(
        self,
        events: EventManager,
        provider: str,
        model: str,
        request_id: Optional[str] = None,
        streaming_options: Optional[Any] = None,
        response_format: Optional[Dict[str, Any]] = None
    ):
        """Initialize streaming bridge.
        
        Args:
            events: EventManager for emitting events
            provider: Provider name
            model: Model name
            request_id: Request ID for tracking
            streaming_options: Optional streaming configuration
        """
        self.events = events
        self.provider = provider
        self.model = model
        self.request_id = request_id
        self.streaming_options = streaming_options
        self.response_format = response_format
        
        # Initialize stream adapter for normalization
        self.adapter = StreamAdapter(provider, model)
        
        # Configure JSON handler if response format provided
        if response_format and response_format.get("type") == "json_schema":
            self.adapter.set_response_format(response_format, True)
        
        # Configure from streaming options
        if streaming_options:
            # JSON handler (if not already set)
            if hasattr(streaming_options, "enable_json_stream_handler"):
                if streaming_options.enable_json_stream_handler and not self.adapter.json_handler:
                    # Use empty format if none provided
                    self.adapter.set_response_format({"type": "json_object"}, True)
            
            # Event processor
            if hasattr(streaming_options, "event_processor"):
                if streaming_options.event_processor:
                    self.adapter.set_event_processor(
                        streaming_options.event_processor,
                        request_id
                    )
            
            # Usage aggregation
            if hasattr(streaming_options, "enable_usage_aggregation"):
                if streaming_options.enable_usage_aggregation:
                    aggregator_type = getattr(streaming_options, "aggregator_type", "auto")
                    prefer_tiktoken = getattr(streaming_options, "prefer_tiktoken", True)
                    self.adapter.configure_usage_aggregation(
                        enable=True,
                        aggregator_type=aggregator_type,
                        prefer_tiktoken=prefer_tiktoken
                    )
        
        # Tracking
        self._start_time = time.time()
        self._chunk_count = 0
        self._collected_text = []
        self._usage_emitted = False
        self._final_usage = None  # Store final usage for retrieval
    
    async def on_start(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Handle stream start event."""
        await self.adapter.start_stream()
        
        event = self.events.create_start_event(
            provider=self.provider,
            model=self.model,
            metadata=metadata or {}
        )
        
        await self.events.emit_event(event)
    
    async def on_delta(self, delta: Union[str, Dict[str, Any]]) -> None:
        """Handle stream delta event.
        
        Args:
            delta: Text chunk or structured delta
        """
        self._chunk_count += 1
        
        # Normalize delta
        if isinstance(delta, str):
            text = delta
            is_json = False
        else:
            # Extract text from structured delta
            normalized = self.adapter.normalize_delta(delta)
            text = normalized.get_text()
            is_json = hasattr(normalized, 'type') and normalized.type == DeltaType.JSON
        
        # Track chunk
        if text:
            await self.adapter.track_chunk(len(text), text)
            self._collected_text.append(text)
        
        # Create event
        event = self.events.create_delta_event(
            delta=delta,
            chunk_index=self._chunk_count,
            provider=self.provider,
            model=self.model,
            is_json=is_json
        )
        
        await self.events.emit_event(event)
    
    async def on_usage(
        self,
        usage: Dict[str, Any],
        is_estimated: bool = False
    ) -> None:
        """Handle usage event.
        
        Args:
            usage: Usage data
            is_estimated: Whether usage is estimated
        """
        if self._usage_emitted:
            return  # Only emit once
        
        self._usage_emitted = True
        self._final_usage = usage  # Store for later retrieval
        
        # Get confidence from aggregator if available
        confidence = 1.0
        if is_estimated and self.adapter.usage_aggregator:
            confidence = self.adapter.usage_aggregator.get_confidence()
        
        event = self.events.create_usage_event(
            usage=usage,
            is_estimated=is_estimated,
            provider=self.provider,
            model=self.model,
            confidence=confidence
        )
        
        await self.events.emit_event(event)
        await self.adapter.emit_usage(usage, is_estimated)
    
    async def on_complete(
        self,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Handle stream completion."""
        await self.adapter.complete_stream()
        
        # Calculate duration
        duration_ms = (time.time() - self._start_time) * 1000
        
        # Get final usage if not already emitted
        final_usage = None
        if not self._usage_emitted and self.adapter.usage_aggregator:
            # Estimate from collected text
            completion_text = "".join(self._collected_text)
            self.adapter.usage_aggregator.add_completion_chunk(completion_text)
            final_usage = self.adapter.usage_aggregator.get_usage()
            await self.on_usage(final_usage, is_estimated=True)
        
        event = self.events.create_complete_event(
            total_chunks=self._chunk_count,
            duration_ms=duration_ms,
            provider=self.provider,
            model=self.model,
            final_usage=final_usage,
            metadata=metadata or {}
        )
        
        await self.events.emit_event(event)
    
    async def on_error(self, error: Exception) -> None:
        """Handle stream error."""
        await self.adapter.complete_stream(error=error)
        
        # Determine if retryable (could use error mapping here)
        is_retryable = any(
            term in str(error).lower()
            for term in ["timeout", "network", "connection", "server error"]
        )
        
        event = self.events.create_error_event(
            error=error,
            error_type=type(error).__name__,
            provider=self.provider,
            model=self.model,
            is_retryable=is_retryable
        )
        
        await self.events.emit_event(event)
    
    def get_final_json(self) -> Optional[Dict[str, Any]]:
        """Get final JSON if JSON handler was used.
        
        Returns:
            Final parsed JSON or None
        """
        if self.adapter.json_handler:
            return self.adapter.get_final_json()
        return None
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get streaming metrics.
        
        Returns:
            Dictionary of metrics
        """
        metrics = self.adapter.get_metrics()
        metrics["usage_emitted"] = self._usage_emitted
        return metrics
    
    def get_collected_text(self) -> str:
        """Get all collected text from streaming.
        
        Returns:
            Concatenated text from all chunks
        """
        return "".join(self._collected_text)
    
    def get_final_usage(self) -> Optional[Dict[str, Any]]:
        """Get final usage data.
        
        Returns:
            Final usage dict or None if not available
        """
        if self._final_usage:
            return self._final_usage
        elif self.adapter.usage_aggregator:
            # Try to get from aggregator if not explicitly emitted
            return self.adapter.usage_aggregator.get_usage()
        return None


def create_callback_wrapper(
    bridge_method: Callable,
    transform: Optional[Callable] = None
) -> Callable:
    """Create a callback wrapper for provider events.
    
    Args:
        bridge_method: Bridge method to call
        transform: Optional transform function for the event data
        
    Returns:
        Wrapped callback function
    """
    async def wrapper(data: Any) -> None:
        if transform:
            data = transform(data)
        await bridge_method(data)
    
    return wrapper