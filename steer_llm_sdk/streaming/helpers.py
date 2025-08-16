"""Helper utilities for common streaming patterns."""

from __future__ import annotations

from typing import AsyncGenerator, Dict, Any, Optional, Tuple, List

from .adapter import StreamAdapter
from .manager import EventManager
from ..models.events import (
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)


class StreamingHelper:
    """Helper for common streaming patterns across providers."""
    
    @staticmethod
    async def collect_with_usage(
        stream: AsyncGenerator,
        adapter: StreamAdapter,
        events: Optional[EventManager] = None
    ) -> Tuple[str, Optional[Dict[str, Any]], Dict[str, Any]]:
        """Collect all chunks and return final text with usage and metrics.
        
        Args:
            stream: Async generator of provider events
            adapter: StreamAdapter configured for the provider
            events: Optional EventManager for emitting events
            
        Returns:
            Tuple of (final_text, usage_data, streaming_metrics)
        """
        await adapter.start_stream()
        chunks: List[str] = []
        usage_data = None
        chunk_index = 0
        
        if events:
            await events.emit_start(events.create_start_event(
                provider=adapter.provider,
                model=adapter.model
            ))
        
        try:
            async for event in stream:
                # Normalize the delta
                delta = adapter.normalize_delta(event)
                text = delta.get_text()
                
                if text:
                    chunks.append(text)
                    await adapter.track_chunk(len(text), text)
                    
                    if events:
                        await events.emit_delta(events.create_delta_event(
                            delta=delta,
                            chunk_index=chunk_index,
                            is_json=adapter.response_format and adapter.response_format.get("type") == "json_object"
                        ))
                    chunk_index += 1
                
                # Check for usage data
                if adapter.should_emit_usage(event):
                    extracted_usage = adapter.extract_usage(event)
                    if extracted_usage:
                        usage_data = extracted_usage
                        if events:
                            await events.emit_usage(events.create_usage_event(
                                usage=usage_data,
                                is_estimated=False,
                                confidence=1.0
                            ))
            
            # Get final metrics
            metrics = adapter.get_metrics()
            final_text = ''.join(chunks)
            
            # Complete the stream
            await adapter.complete_stream(final_usage=usage_data)
            
            if events:
                await events.emit_complete(events.create_complete_event(
                    total_chunks=chunk_index,
                    duration_ms=metrics.get("duration_seconds", 0) * 1000,
                    final_usage=usage_data
                ))
            
            return final_text, usage_data, metrics
            
        except Exception as e:
            await adapter.complete_stream(error=e)
            if events:
                await events.emit_error(events.create_error_event(
                    error=e,
                    error_type=type(e).__name__,
                    is_retryable=adapter._is_retryable_error(e)
                ))
            raise
    
    @staticmethod
    async def stream_with_events(
        stream: AsyncGenerator,
        adapter: StreamAdapter,
        events: EventManager
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks while emitting events.
        
        Args:
            stream: Async generator of provider events
            adapter: StreamAdapter configured for the provider
            events: EventManager for emitting events
            
        Yields:
            Text chunks from the stream
        """
        await adapter.start_stream()
        chunk_index = 0
        
        await events.emit_start(events.create_start_event(
            provider=adapter.provider,
            model=adapter.model
        ))
        
        try:
            async for event in stream:
                # Normalize the delta
                delta = adapter.normalize_delta(event)
                text = delta.get_text()
                
                if text:
                    await adapter.track_chunk(len(text), text)
                    await events.emit_delta(events.create_delta_event(
                        delta=delta,
                        chunk_index=chunk_index,
                        is_json=adapter.response_format and adapter.response_format.get("type") == "json_object"
                    ))
                    chunk_index += 1
                    yield text
                
                # Check for usage data
                if adapter.should_emit_usage(event):
                    extracted_usage = adapter.extract_usage(event)
                    if extracted_usage:
                        await events.emit_usage(events.create_usage_event(
                            usage=extracted_usage,
                            is_estimated=False,
                            confidence=1.0
                        ))
            
            # Get metrics and complete
            metrics = adapter.get_metrics()
            await adapter.complete_stream()
            
            await events.emit_complete(events.create_complete_event(
                total_chunks=chunk_index,
                duration_ms=metrics.get("duration_seconds", 0) * 1000,
                final_usage=None  # Usage was already emitted if available
            ))
            
        except Exception as e:
            await adapter.complete_stream(error=e)
            await events.emit_error(events.create_error_event(
                error=e,
                error_type=type(e).__name__,
                is_retryable=adapter._is_retryable_error(e)
            ))
            raise