"""Main client interface for Steer LLM SDK."""

import asyncio
import time
from typing import Optional, List, Union, Dict, Any, Callable, Awaitable
from ..core.routing import LLMRouter
from ..models.conversation_types import ConversationMessage
from ..models.generation import GenerationResponse
from ..models.events import (
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)
from ..streaming.manager import EventManager
from ..streaming.processor import create_event_processor
from ..streaming.helpers import StreamingHelper
from ..streaming.adapter import StreamAdapter
from ..observability import MetricsCollector, MetricsConfig, get_collector
from ..observability.sinks import MetricsSink


class SteerLLMClient:
    """High-level client for Steer LLM SDK."""
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        xai_api_key: Optional[str] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        metrics_config: Optional[MetricsConfig] = None,
        metrics_sinks: Optional[List[MetricsSink]] = None
    ):
        """
        Initialize the client.
        
        Args:
            openai_api_key: Optional OpenAI API key
            anthropic_api_key: Optional Anthropic API key
            xai_api_key: Optional xAI API key
            metrics_collector: Optional metrics collector instance
            metrics_config: Optional metrics configuration
            metrics_sinks: Optional list of metrics sinks
        """
        # Initialize router with API keys
        self.router = LLMRouter(
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
            xai_api_key=xai_api_key
        )
        
        # Set up metrics
        if metrics_collector:
            self.metrics_collector = metrics_collector
        else:
            # Use global collector or create one
            self.metrics_collector = get_collector()
            if metrics_config:
                self.metrics_collector.config = metrics_config
        
        # Add any provided sinks
        if metrics_sinks:
            for sink in metrics_sinks:
                self.metrics_collector.add_sink(sink)
    
    async def generate(
        self,
        messages: Union[str, List[ConversationMessage]],
        model: str = None,
        llm_model_id: str = None,
        temperature: float = None,
        max_tokens: int = None,
        raw_params: Dict[str, Any] = None,
        **kwargs
    ) -> GenerationResponse:
        """Generate text using specified model.
        
        Args:
            messages: Input messages (string or list of ConversationMessage)
            model: Model name (deprecated, use llm_model_id)
            llm_model_id: Model ID (preferred)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            raw_params: Dictionary of all parameters (takes precedence)
            **kwargs: Additional parameters
            
        Returns:
            GenerationResponse: Response object containing text, usage, cost info, etc.
        """
        # Determine model ID (llm_model_id takes precedence)
        model_id = llm_model_id or model or "GPT-4o Mini"

        # Allow model-aware defaults if not provided
        if (temperature is None) or (max_tokens is None):
            from ..core.routing import get_config
            cfg = get_config(model_id)
            if temperature is None:
                temperature = cfg.temperature
            if max_tokens is None:
                max_tokens = cfg.max_tokens

        # Build parameters dict
        if raw_params is not None:
            # raw_params takes precedence
            params = raw_params.copy()
            # Add any kwargs not in raw_params
            for k, v in kwargs.items():
                if k not in params:
                    params[k] = v
        else:
            # Build from individual params
            params = kwargs.copy()
            if temperature is not None:
                params["temperature"] = temperature
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
        
        # Get provider from model config
        from ..core.routing import get_config
        config = get_config(model_id)
        provider = config.provider.value if hasattr(config.provider, 'value') else str(config.provider)
        
        # Track metrics
        async with self.metrics_collector.track_request(
            provider=provider,
            model=model_id,
            method="generate"
        ) as request_metrics:
            response = await self.router.generate(messages, model_id, params)
            
            # Update metrics with usage data
            if hasattr(response, 'usage') and response.usage:
                request_metrics.prompt_tokens = getattr(response.usage, 'prompt_tokens', 0)
                request_metrics.completion_tokens = getattr(response.usage, 'completion_tokens', 0)
                request_metrics.total_tokens = getattr(response.usage, 'total_tokens', 0)
                request_metrics.cached_tokens = getattr(response.usage, 'cached_tokens', 0)
            
            return response
    
    async def stream_with_usage(
        self,
        messages: Union[str, List[ConversationMessage]],
        model: str = "GPT-4o Mini",
        temperature: float = None,
        max_tokens: int = None,
        streaming_options: Optional["StreamingOptions"] = None,
        on_start: Optional[Callable[[StreamStartEvent], Awaitable[None]]] = None,
        on_delta: Optional[Callable[[StreamDeltaEvent], Awaitable[None]]] = None,
        on_usage: Optional[Callable[[StreamUsageEvent], Awaitable[None]]] = None,
        on_complete: Optional[Callable[[StreamCompleteEvent], Awaitable[None]]] = None,
        on_error: Optional[Callable[[StreamErrorEvent], Awaitable[None]]] = None,
        **kwargs
    ):
        """Stream text generation and return usage data.
        
        Args:
            messages: Input messages
            model: Model to use
            temperature: Temperature setting
            max_tokens: Max tokens to generate
            streaming_options: Streaming configuration options
            on_start: Callback when streaming starts
            on_delta: Callback for each text chunk
            on_usage: Callback when usage data is available
            on_complete: Callback when streaming completes
            on_error: Callback when an error occurs
            **kwargs: Additional parameters
        
        Returns:
            StreamingResponseWithUsage: Object containing full text and usage data
        """
        # Allow model-aware defaults
        if temperature is None or max_tokens is None:
            from ..core.routing import get_config
            cfg = get_config(model)
            if temperature is None:
                temperature = cfg.temperature
            if max_tokens is None:
                max_tokens = cfg.max_tokens
        params = {"temperature": temperature, "max_tokens": max_tokens, **kwargs}
        
        # Import required modules
        from ..models.generation import StreamingResponseWithUsage
        from ..models.streaming import StreamingOptions, JSON_MODE_OPTIONS
        
        # Handle streaming options
        if streaming_options is None:
            # Check if JSON mode is requested
            rf = params.get("response_format") if isinstance(params, dict) else None
            if isinstance(rf, dict) and rf.get("type") == "json_object":
                streaming_options = JSON_MODE_OPTIONS
            else:
                streaming_options = StreamingOptions()
        
        # Extract legacy enable_json_stream_handler if provided
        if "enable_json_stream_handler" in kwargs:
            streaming_options.enable_json_stream_handler = kwargs.pop("enable_json_stream_handler")
        
        # Configure event processor if not already provided
        if not hasattr(streaming_options, 'event_processor') or not streaming_options.event_processor:
            # Create default event processor with correlation and timestamps
            event_processor = create_event_processor(
                add_correlation=True,
                add_timestamp=True,
                background=False
            )
            streaming_options.event_processor = event_processor
        
        # Pass streaming options to router
        params["streaming_options"] = streaming_options
        
        # Get provider from model config
        from ..core.routing import get_config
        config = get_config(model)
        provider = config.provider.value if hasattr(config.provider, 'value') else str(config.provider)
        
        # Create stream adapter
        adapter = StreamAdapter(provider)
        adapter.model = model
        
        # Configure adapter with response format for JSON mode
        rf = params.get("response_format") if isinstance(params, dict) else None
        if isinstance(rf, dict) and rf.get("type") == "json_object":
            adapter.response_format = rf
        
        # Attach event processor to adapter if we have one
        if hasattr(streaming_options, 'event_processor') and streaming_options.event_processor:
            adapter.set_event_processor(streaming_options.event_processor)
        
        response_wrapper = StreamingResponseWithUsage()
        
        # Track metrics
        async with self.metrics_collector.track_request(
            provider=provider,
            model=model,
            method="stream"
        ) as request_metrics:
            # Create event manager if callbacks provided (backward compat)
            events = None
            if any([on_start, on_delta, on_usage, on_complete, on_error]):
                events = EventManager(
                    on_start=on_start,
                    on_delta=on_delta,
                    on_usage=on_usage,
                    on_complete=on_complete,
                    on_error=on_error
                )
            
            # Use StreamingHelper to collect chunks and usage
            text, usage_data, metrics = await StreamingHelper.collect_with_usage(
                self.router.generate_stream(messages, model, params, True),
                adapter,
                events
            )
            
            # Update response wrapper
            response_wrapper.add_chunk(text)
            if usage_data:
                response_wrapper.set_usage(
                    usage=usage_data,
                    model=model,
                    provider=provider
                )
                # Update request metrics
                request_metrics.prompt_tokens = usage_data.get('prompt_tokens', 0)
                request_metrics.completion_tokens = usage_data.get('completion_tokens', 0)
                request_metrics.total_tokens = usage_data.get('total_tokens', 0)
                request_metrics.cached_tokens = usage_data.get('cached_tokens', 0)
            
            # Handle JSON if needed
            if adapter.response_format and adapter.response_format.get("type") == "json_object":
                try:
                    import json
                    final_json = json.loads(text)
                    response_wrapper.set_final_json(final_json)
                except:
                    pass  # Invalid JSON, keep as text
            
            # Set TTFT if available
            if 'time_to_first_token_seconds' in metrics:
                request_metrics.time_to_first_token_ms = metrics['time_to_first_token_seconds'] * 1000
            
            return response_wrapper
    
    async def stream(
        self,
        messages: Union[str, List[ConversationMessage]],
        model: str = "GPT-4o Mini",
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ):
        """Stream text generation.
        
        Yields text chunks. For a summarized result with usage, use stream_with_usage().
        """
        if "return_usage" in kwargs:
            raise ValueError("stream(...): 'return_usage' is not supported. Use stream_with_usage(...) instead.")
        # Allow model-aware defaults
        if temperature is None or max_tokens is None:
            from ..core.routing import get_config
            cfg = get_config(model)
            if temperature is None:
                temperature = cfg.temperature
            if max_tokens is None:
                max_tokens = cfg.max_tokens
        params = {"temperature": temperature, "max_tokens": max_tokens, **kwargs}
        async for chunk in self.router.generate_stream(messages, model, params):
            yield chunk
    
    def get_available_models(self):
        """Get list of available models."""
        from ..core.routing import get_available_models
        return get_available_models()
    
    def check_model_availability(self, model: str) -> bool:
        """Check if a specific model is available."""
        from ..core.routing import check_lightweight_availability
        return check_lightweight_availability(model)


# Convenience function for quick usage
async def generate(
    prompt: str,
    model: str = "GPT-4o Mini",
    temperature: float = None,
    max_tokens: int = None,
    **kwargs
) -> str:
    """Quick generation function that returns just the text."""
    client = SteerLLMClient()
    response = await client.generate(prompt, model=model, temperature=temperature, max_tokens=max_tokens, **kwargs)
    return response.text