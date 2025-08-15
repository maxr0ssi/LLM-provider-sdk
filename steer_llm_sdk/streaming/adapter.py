from __future__ import annotations

import time
from typing import Any, Dict, Optional, Union, List

from .types import StreamDelta, DeltaType
from .json_handler import JsonStreamHandler
from .aggregator import UsageAggregator, create_usage_aggregator
from .processor import EventProcessor
from ..models.events import (
    StreamEvent,
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)


class StreamAdapter:
    """Adapter for normalizing streaming responses across different LLM providers.
    
    This class handles provider-specific delta formats, usage extraction,
    and streaming metrics tracking.
    """
    
    def __init__(self, provider: str, model: Optional[str] = None):
        """Initialize StreamAdapter with provider name.
        
        Args:
            provider: Name of the provider (openai, anthropic, xai)
            model: Model name for usage aggregation
        """
        self.provider = provider.lower()
        self.model = model
        self._chunk_count = 0
        self._start_time: Optional[float] = None
        self._total_chars = 0
        self.json_handler: Optional[JsonStreamHandler] = None
        self.response_format: Optional[Dict[str, Any]] = None
        self.enable_json_handler = False
        self.usage_aggregator: Optional[UsageAggregator] = None
        self.enable_usage_aggregation = False
        self._messages = None
        self.event_processor: Optional[EventProcessor] = None
        self._request_id: Optional[str] = None
        self._stream_completed: bool = False
    
    def set_response_format(self, response_format: Optional[Dict[str, Any]], enable_json_handler: bool = False):
        """Set response format to enable JSON handling.
        
        Args:
            response_format: Response format configuration
            enable_json_handler: Whether to enable JSON stream handler
        """
        self.response_format = response_format
        self.enable_json_handler = enable_json_handler
        
        if enable_json_handler and response_format and response_format.get("type") == "json_object":
            self.json_handler = JsonStreamHandler()
    
    def configure_usage_aggregation(
        self, 
        enable: bool = True,
        messages: Optional[Any] = None,
        aggregator_type: str = "auto",
        prefer_tiktoken: bool = True
    ):
        """Configure usage aggregation for providers without streaming usage.
        
        Args:
            enable: Whether to enable usage aggregation
            messages: Messages/prompt for token counting
            aggregator_type: Type of aggregator ('auto', 'tiktoken', 'character')
            prefer_tiktoken: Whether to prefer tiktoken when available
        """
        self.enable_usage_aggregation = enable
        self._messages = messages
        
        if enable and self.model:
            if aggregator_type == "tiktoken":
                from .aggregator import TiktokenAggregator
                try:
                    self.usage_aggregator = TiktokenAggregator(self.model, self.provider)
                except ImportError:
                    # Fall back to character
                    self.usage_aggregator = create_usage_aggregator(
                        self.model, self.provider, prefer_tiktoken=False
                    )
            elif aggregator_type == "character":
                self.usage_aggregator = create_usage_aggregator(
                    self.model, self.provider, prefer_tiktoken=False
                )
            else:  # auto
                self.usage_aggregator = create_usage_aggregator(
                    self.model, self.provider, prefer_tiktoken=prefer_tiktoken
                )
            
            # Estimate prompt tokens if messages provided
            if self._messages and self.usage_aggregator:
                self.usage_aggregator.estimate_prompt_tokens(self._messages)
    
    def set_event_processor(self, processor: Optional[EventProcessor], request_id: Optional[str] = None):
        """Set event processor for streaming events.
        
        Args:
            processor: Event processor to use
            request_id: Request ID for event tracking
        """
        self.event_processor = processor
        self._request_id = request_id
    
    async def emit_event(self, event: StreamEvent) -> Optional[StreamEvent]:
        """Emit an event through the processor if configured.
        
        Args:
            event: Event to emit
            
        Returns:
            Processed event or original if no processor
        """
        if self.event_processor:
            # Add common metadata
            event.provider = self.provider
            event.model = self.model
            event.request_id = self._request_id
            
            # Process event
            return await self.event_processor.process_event(event)
        return event
    
    def normalize_delta(self, provider_delta: Any) -> StreamDelta:
        """Normalize provider-specific delta to standard StreamDelta.
        
        Args:
            provider_delta: Raw delta from provider API
            
        Returns:
            Normalized StreamDelta object
        """
        # Get base delta from provider
        if self.provider == "openai":
            delta = self._normalize_openai_delta(provider_delta)
        elif self.provider == "anthropic":
            delta = self._normalize_anthropic_delta(provider_delta)
        elif self.provider == "xai":
            delta = self._normalize_xai_delta(provider_delta)
        else:
            delta = self._normalize_generic_delta(provider_delta)
        
        # Track completion text for usage aggregation
        if self.usage_aggregator and delta.kind == "text" and delta.value:
            self.usage_aggregator.add_completion_chunk(str(delta.value))
        
        # If JSON mode enabled and we have text, process through handler
        if self.json_handler and delta.kind == "text" and delta.value:
            json_obj = self.json_handler.process_chunk(str(delta.value))
            if json_obj:
                return StreamDelta(
                    kind="json",
                    value=json_obj,
                    provider=delta.provider,
                    raw_event=delta.raw_event,
                    metadata={
                        **(delta.metadata or {}),
                        "complete_json": True,
                        "json_handler": True
                    }
                )
                
        return delta
    
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
        
        xAI doesn't provide usage in streaming, use aggregator if enabled.
        """
        if self.usage_aggregator and self.enable_usage_aggregation:
            return self.usage_aggregator.get_usage()
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
    
    async def start_stream(self):
        """Mark the start of streaming."""
        self._start_time = time.time()
        self._chunk_count = 0
        self._total_chars = 0
        
        # Emit start event
        await self.emit_event(StreamStartEvent(
            stream_id=self._request_id
        ))
    
    async def track_chunk(self, chunk_size: int, delta: Optional[Any] = None):
        """Track a chunk for metrics and emit delta event.
        
        Args:
            chunk_size: Size of the chunk in characters
            delta: Optional delta content
        """
        self._chunk_count += 1
        self._total_chars += chunk_size
        
        # Emit delta event
        if delta is not None:
            await self.emit_event(StreamDeltaEvent(
                delta=delta,
                chunk_index=self._chunk_count - 1,
                is_json=self.response_format and self.response_format.get("type") == "json_object"
            ))
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get streaming metrics.
        
        Returns:
            Dictionary with streaming metrics
        """
        duration = time.time() - self._start_time if self._start_time else 0
        metrics = {
            "chunks": self._chunk_count,
            "total_chars": self._total_chars,
            "duration_seconds": duration,
            "chunks_per_second": self._chunk_count / duration if duration > 0 else 0,
            "chars_per_second": self._total_chars / duration if duration > 0 else 0
        }
        
        # Add JSON handler metrics if available
        if self.json_handler:
            json_stats = self.json_handler.get_statistics()
            metrics["json_objects_found"] = json_stats["objects_found"]
            metrics["json_buffer_size"] = json_stats["buffer_size"]
        
        # Add aggregator metrics if available
        if self.usage_aggregator:
            usage_data = self.usage_aggregator.get_usage()
            metrics["aggregated_prompt_tokens"] = usage_data["prompt_tokens"]
            metrics["aggregated_completion_tokens"] = usage_data["completion_tokens"]
            metrics["aggregation_method"] = usage_data["method"]
            metrics["aggregation_confidence"] = usage_data["confidence"]
            
        return metrics
    
    def get_aggregated_usage(self) -> Optional[Dict[str, Any]]:
        """Get aggregated usage data if available.
        
        Returns:
            Usage data from aggregator, or None if not available
        """
        if self.usage_aggregator and self.enable_usage_aggregation:
            return self.usage_aggregator.get_usage()
        return None
    
    def get_final_json(self) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """Get the final JSON object if JSON handler is enabled.
        
        Returns:
            Final JSON object/array, or None if not available
        """
        if self.json_handler:
            return self.json_handler.get_final_object()
        return None
    
    def get_all_json_objects(self) -> List[Union[Dict[str, Any], List[Any]]]:
        """Get all JSON objects found during streaming.
        
        Returns:
            List of all JSON objects/arrays found
        """
        if self.json_handler:
            return self.json_handler.get_all_objects()
        return []
    
    async def emit_usage(self, usage: Dict[str, Any], is_estimated: bool = False):
        """Emit usage event.
        
        Args:
            usage: Usage data dictionary
            is_estimated: Whether usage is estimated
        """
        confidence = 1.0
        if is_estimated and self.usage_aggregator:
            confidence = getattr(self.usage_aggregator, 'confidence', 0.5)
        
        await self.emit_event(StreamUsageEvent(
            usage=usage,
            is_estimated=is_estimated,
            confidence=confidence
        ))
    
    async def complete_stream(self, final_usage: Optional[Dict[str, Any]] = None, error: Optional[Exception] = None):
        """Complete the stream and emit appropriate event.
        
        Args:
            final_usage: Final usage data if available
            error: Error if stream failed
        """
        if self._stream_completed:
            return  # Already completed
            
        self._stream_completed = True
        duration_ms = (time.time() - self._start_time) * 1000 if self._start_time else 0
        
        if error:
            await self.emit_event(StreamErrorEvent(
                error=error,
                is_retryable=self._is_retryable_error(error)
            ))
        else:
            await self.emit_event(StreamCompleteEvent(
                total_chunks=self._chunk_count,
                duration_ms=duration_ms,
                final_usage=final_usage
            ))
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if error is retryable based on provider."""
        # This is a simplified check - real implementation would use ErrorMapper
        error_type = type(error).__name__
        retryable_types = ["RateLimitError", "InternalServerError", "TimeoutError"]
        return any(t in error_type for t in retryable_types)


