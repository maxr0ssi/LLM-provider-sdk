"""Main entry point for Steer LLM SDK."""

import asyncio
from typing import Optional, List, Union, Dict, Any
from .llm.router import LLMRouter
from .models.conversation_types import ConversationMessage


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
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ):
        """Stream text generation and return usage data.
        
        Returns:
            StreamingResponseWithUsage: Object containing full text and usage data
        """
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        from .models.generation import StreamingResponseWithUsage
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
        
        return response_wrapper
    
    async def stream(
        self,
        messages: Union[str, List[ConversationMessage]],
        model: str = "GPT-4o Mini",
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ):
        """Stream text generation.
        
        Args:
            messages: Input messages
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Yields:
            str: Text chunks
        """
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        # Stream chunks
        async for chunk in self.router.generate_stream(messages, model, params):
            yield chunk
    
    def get_available_models(self):
        """Get list of available models."""
        from .llm.registry import get_available_models
        return get_available_models()
    
    def check_model_availability(self, model: str) -> bool:
        """Check if a specific model is available."""
        from .llm.registry import check_lightweight_availability
        return check_lightweight_availability(model)


# Convenience function for quick usage
async def generate(
    prompt: str,
    model: str = "GPT-4o Mini",
    temperature: float = 0.7,
    max_tokens: int = 512,
    **kwargs
) -> str:
    """Quick generation function."""
    client = SteerLLMClient()
    return await client.generate(prompt, model, temperature, max_tokens, **kwargs)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Steer LLM SDK CLI")
    parser.add_argument("prompt", help="Text prompt for generation")
    parser.add_argument("--model", default="GPT-4o Mini", help="Model to use")
    parser.add_argument("--temperature", type=float, default=0.7, help="Temperature for generation")
    parser.add_argument("--max-tokens", type=int, default=512, help="Maximum tokens to generate")
    
    args = parser.parse_args()
    
    # Run generation
    result = asyncio.run(generate(
        args.prompt,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens
    ))
    
    print(result)


if __name__ == "__main__":
    main()