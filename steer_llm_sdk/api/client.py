"""Main client interface for Steer LLM SDK."""

import asyncio
from typing import Optional, List, Union, Dict, Any
from ..core.routing import LLMRouter
from ..models.conversation_types import ConversationMessage


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
        **kwargs
    ):
        """Stream text generation and return usage data.
        
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
        
        from ..models.generation import StreamingResponseWithUsage
        response_wrapper = StreamingResponseWithUsage()
        
        async for item in self.router.generate_stream(messages, model, params, return_usage=True):
            if isinstance(item, tuple):
                # Provider returned (chunk, usage_data)
                chunk, usage_data = item
                if chunk is not None:
                    response_wrapper.add_chunk(chunk)
                if usage_data is not None:
                    # Final usage data
                    response_wrapper.set_usage(**usage_data)
            else:
                # Just a chunk
                response_wrapper.add_chunk(item)
        
        # Post-process JSON-object streaming to avoid duplicate objects when providers
        # emit full objects alongside deltas. If response_format requests a JSON object,
        # collapse to the last complete JSON object in the concatenated text.
        try:
            rf = params.get("response_format") if isinstance(params, dict) else None
            if isinstance(rf, dict) and rf.get("type") == "json_object":
                combined = response_wrapper.get_text()
                # Find the last complete JSON object heuristically
                start = combined.rfind("{")
                end = combined.rfind("}")
                if start != -1 and end != -1 and end > start:
                    candidate = combined[start:end+1]
                    import json  # Local import to avoid overhead when not needed
                    try:
                        json.loads(candidate)
                        # Replace chunks with just the single JSON object
                        response_wrapper.chunks = [candidate]
                    except Exception as e:
                        raise Exception(f"Failed to post-process JSON-object streaming: {e}")
        except Exception as e:
            raise Exception(f"Failed to post-process JSON-object streaming: {e}")

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