"""Main client interface for Steer LLM SDK."""

import asyncio
from typing import Optional, List, Union, Dict, Any, Callable, Awaitable
from ..core.routing import LLMRouter
from ..models.conversation_types import ConversationMessage
from ..models.events import (
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)
from ..streaming.manager import EventManager
from ..streaming.processor import create_event_processor


class SteerLLMClient:
    """High-level client for Steer LLM SDK."""
    
    def __init__(self):
        self.router = LLMRouter()
    
    async def generate(
        self,
        messages: Union[str, List[ConversationMessage]],
        model: str = None,
        llm_model_id: str = None,
        temperature: float = None,
        max_tokens: int = None,
        raw_params: Dict[str, Any] = None,
        **kwargs
    ) -> str:
        """Generate text using specified model.
        
        Args:
            messages: Input messages (string or list of ConversationMessage)
            model: Model name (deprecated, use llm_model_id)
            llm_model_id: Model ID (preferred)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            raw_params: Dictionary of all parameters (takes precedence)
            **kwargs: Additional parameters
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
        
        response = await self.router.generate(messages, model_id, params)
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
        
        # Configure event callbacks if provided
        if any([on_start, on_delta, on_usage, on_complete, on_error]):
            # Create event manager with callbacks
            event_manager = EventManager(
                on_start=on_start,
                on_delta=on_delta,
                on_usage=on_usage,
                on_complete=on_complete,
                on_error=on_error
            )
            
            # Create event processor that uses the event manager
            event_processor = create_event_processor(
                add_correlation=True,
                add_timestamp=True,
                background=False
            )
            
            # Add event manager as a custom transformer
            class EventManagerTransformer:
                def __init__(self, manager):
                    self.manager = manager
                
                async def transform(self, event):
                    # Emit to event manager
                    await self.manager.emit_event(event)
                    return event
            
            event_processor.add_transformer(EventManagerTransformer(event_manager))
            streaming_options.event_processor = event_processor
        
        # Pass streaming options to router
        params["streaming_options"] = streaming_options
        
        response_wrapper = StreamingResponseWithUsage()
        
        async for item in self.router.generate_stream(messages, model, params, return_usage=True):
            if isinstance(item, tuple):
                # Provider returned (chunk, usage_data)
                chunk, usage_data = item
                if chunk is not None:
                    response_wrapper.add_chunk(chunk)
                if usage_data is not None:
                    # Extract final JSON if available
                    final_json = usage_data.pop("final_json", None)
                    # Set usage data (without final_json)
                    response_wrapper.set_usage(**usage_data)
                    # Set final JSON if available
                    if final_json is not None:
                        response_wrapper.set_final_json(final_json)
            else:
                # Just a chunk
                response_wrapper.add_chunk(item)
        
        # Handle JSON post-processing if enabled
        if streaming_options.enable_json_stream_handler:
            rf = params.get("response_format") if isinstance(params, dict) else None
            if isinstance(rf, dict) and rf.get("type") == "json_object":
                # Use the final JSON from the handler if available
                final_json = response_wrapper.get_json()
                if final_json is not None:
                    # Replace chunks with the properly parsed JSON
                    import json
                    response_wrapper.chunks = [json.dumps(final_json)]
                else:
                    # Fallback to heuristic only if handler didn't provide JSON
                    combined = response_wrapper.get_text()
                    start = combined.rfind("{")
                    end = combined.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        candidate = combined[start:end+1]
                        try:
                            json.loads(candidate)
                            response_wrapper.chunks = [candidate]
                        except Exception:
                            # If parsing fails, keep original chunks
                            pass

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