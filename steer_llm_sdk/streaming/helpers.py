"""Helper utilities for common streaming patterns."""

from __future__ import annotations

from typing import AsyncGenerator, Dict, Any, Optional, Tuple, List

from .adapter import StreamAdapter
from .manager import EventManager


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
        adapter.start_stream()
        chunks: List[str] = []
        usage_data = None
        
        if events:
            await events.emit_start({
                "provider": adapter.provider,
                "stream_start": True
            })
        
        try:
            async for event in stream:
                # Normalize the delta
                delta = adapter.normalize_delta(event)
                text = delta.get_text()
                
                if text:
                    chunks.append(text)
                    adapter.track_chunk(len(text))
                    
                    if events:
                        await events.emit_delta(delta)
                
                # Check for usage data
                if adapter.should_emit_usage(event):
                    extracted_usage = adapter.extract_usage(event)
                    if extracted_usage:
                        usage_data = extracted_usage
                        if events:
                            await events.emit_usage(usage_data)
            
            # Get final metrics
            metrics = adapter.get_metrics()
            final_text = ''.join(chunks)
            
            if events:
                await events.emit_complete({
                    "provider": adapter.provider,
                    "final_text": final_text,
                    "metrics": metrics
                })
            
            return final_text, usage_data, metrics
            
        except Exception as e:
            if events:
                await events.emit_error(e)
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
        adapter.start_stream()
        
        await events.emit_start({
            "provider": adapter.provider,
            "stream_start": True
        })
        
        try:
            async for event in stream:
                # Normalize the delta
                delta = adapter.normalize_delta(event)
                text = delta.get_text()
                
                if text:
                    adapter.track_chunk(len(text))
                    await events.emit_delta(delta)
                    yield text
                
                # Check for usage data
                if adapter.should_emit_usage(event):
                    extracted_usage = adapter.extract_usage(event)
                    if extracted_usage:
                        await events.emit_usage(extracted_usage)
            
            # Emit completion event with metrics
            metrics = adapter.get_metrics()
            await events.emit_complete({
                "provider": adapter.provider,
                "metrics": metrics
            })
            
        except Exception as e:
            await events.emit_error(e)
            raise