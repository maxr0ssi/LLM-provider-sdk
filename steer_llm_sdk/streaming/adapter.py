from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .types import StreamDelta, DeltaType


class StreamAdapter:
    """Adapter for normalizing streaming responses across different LLM providers.
    
    This class handles provider-specific delta formats, usage extraction,
    and streaming metrics tracking.
    """
    
    def __init__(self, provider: str):
        """Initialize StreamAdapter with provider name.
        
        Args:
            provider: Name of the provider (openai, anthropic, xai)
        """
        self.provider = provider.lower()
        self._chunk_count = 0
        self._start_time: Optional[float] = None
        self._total_chars = 0
    
    def normalize_delta(self, provider_delta: Any) -> StreamDelta:
        """Normalize provider-specific delta to standard StreamDelta.
        
        Args:
            provider_delta: Raw delta from provider API
            
        Returns:
            Normalized StreamDelta object
        """
        # Provider-specific handling
        if self.provider == "openai":
            return self._normalize_openai_delta(provider_delta)
        elif self.provider == "anthropic":
            return self._normalize_anthropic_delta(provider_delta)
        elif self.provider == "xai":
            return self._normalize_xai_delta(provider_delta)
        
        # Fallback to generic normalization
        return self._normalize_generic_delta(provider_delta)
    
    def _normalize_openai_delta(self, delta: Any) -> StreamDelta:
        """Normalize OpenAI's chunk.choices[0].delta.content structure."""
        text = ""
        
        # Handle OpenAI's nested structure
        if hasattr(delta, 'choices') and delta.choices:
            choice = delta.choices[0]
            if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                text = choice.delta.content or ""
        
        return StreamDelta(
            kind="text",
            value=text,
            provider="openai",
            raw_event=delta,
            metadata={"chunk_id": self._chunk_count}
        )
    
    def _normalize_anthropic_delta(self, delta: Any) -> StreamDelta:
        """Normalize Anthropic's event.delta.text structure."""
        text = ""
        event_type = getattr(delta, 'type', None)
        
        # Handle Anthropic's event types
        if event_type == "content_block_delta":
            if hasattr(delta, 'delta') and hasattr(delta.delta, 'text'):
                text = delta.delta.text or ""
        
        return StreamDelta(
            kind="text",
            value=text,
            provider="anthropic",
            raw_event=delta,
            metadata={
                "chunk_id": self._chunk_count,
                "event_type": event_type
            }
        )
    
    def _normalize_xai_delta(self, delta: Any) -> StreamDelta:
        """Normalize xAI's chunk.content structure."""
        text = ""
        
        # xAI returns tuples of (response, chunk)
        if isinstance(delta, tuple) and len(delta) == 2:
            _, chunk = delta
            if hasattr(chunk, 'content'):
                text = chunk.content or ""
        elif hasattr(delta, 'content'):
            text = delta.content or ""
        
        return StreamDelta(
            kind="text",
            value=text,
            provider="xai",
            raw_event=delta,
            metadata={"chunk_id": self._chunk_count}
        )
    
    def _normalize_generic_delta(self, provider_delta: Any) -> StreamDelta:
        """Fallback normalization for unknown providers."""
        if isinstance(provider_delta, (dict, list)):
            return StreamDelta(
                kind="json",
                value=provider_delta,
                provider=self.provider,
                raw_event=provider_delta
            )
        
        text = None
        if hasattr(provider_delta, "delta"):
            text = getattr(provider_delta, "delta")
        if hasattr(provider_delta, "text") and not text:
            text = getattr(provider_delta, "text")
        
        return StreamDelta(
            kind="text",
            value=str(text if text is not None else provider_delta),
            provider=self.provider,
            raw_event=provider_delta
        )
    
    def extract_usage(self, event: Any) -> Optional[Dict[str, Any]]:
        """Extract usage data from provider-specific events.
        
        Args:
            event: Raw event from provider API
            
        Returns:
            Usage dictionary or None if no usage data
        """
        if self.provider == "openai":
            return self._extract_openai_usage(event)
        elif self.provider == "anthropic":
            return self._extract_anthropic_usage(event)
        elif self.provider == "xai":
            return self._extract_xai_usage(event)
        
        return None
    
    def _extract_openai_usage(self, event: Any) -> Optional[Dict[str, Any]]:
        """Extract usage from OpenAI events."""
        if hasattr(event, 'usage') and event.usage is not None:
            try:
                usage_dict = event.usage.model_dump() if hasattr(event.usage, 'model_dump') else dict(event.usage.__dict__)
                return usage_dict
            except Exception:
                pass
        return None
    
    def _extract_anthropic_usage(self, event: Any) -> Optional[Dict[str, Any]]:
        """Extract usage from Anthropic events."""
        # Anthropic sends usage in message_delta events
        if hasattr(event, 'usage'):
            try:
                usage_dict = event.usage.model_dump() if hasattr(event.usage, 'model_dump') else event.usage.__dict__
                return usage_dict
            except Exception:
                pass
        return None
    
    def _extract_xai_usage(self, event: Any) -> Optional[Dict[str, Any]]:
        """Extract usage from xAI events.
        
        Note: xAI doesn't provide usage in streaming, this is a placeholder.
        """
        return None
    
    def should_emit_usage(self, event: Any) -> bool:
        """Determine if this event contains final usage data.
        
        Args:
            event: Raw event from provider API
            
        Returns:
            True if this event contains final usage data
        """
        if self.provider == "openai":
            # OpenAI sends usage with the final chunk
            return hasattr(event, 'usage') and event.usage is not None
        elif self.provider == "anthropic":
            # Anthropic sends usage in message_stop event
            return getattr(event, 'type', None) == "message_stop"
        elif self.provider == "xai":
            # xAI doesn't provide usage in streaming
            return False
        
        return False
    
    def start_stream(self):
        """Mark the start of streaming."""
        self._start_time = time.time()
        self._chunk_count = 0
        self._total_chars = 0
    
    def track_chunk(self, chunk_size: int):
        """Track a chunk for metrics.
        
        Args:
            chunk_size: Size of the chunk in characters
        """
        self._chunk_count += 1
        self._total_chars += chunk_size
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get streaming metrics.
        
        Returns:
            Dictionary with streaming metrics
        """
        duration = time.time() - self._start_time if self._start_time else 0
        return {
            "chunks": self._chunk_count,
            "total_chars": self._total_chars,
            "duration_seconds": duration,
            "chunks_per_second": self._chunk_count / duration if duration > 0 else 0,
            "chars_per_second": self._total_chars / duration if duration > 0 else 0
        }


