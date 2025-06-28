"""Main entry point for Steer LLM SDK."""

import asyncio
from typing import Optional, List, Union
from .llm.router import LLMRouter
from .models.conversation_types import ConversationMessage


class SteerLLMClient:
    """High-level client for Steer LLM SDK."""
    
    def __init__(self):
        self.router = LLMRouter()
    
    async def generate(
        self,
        messages: Union[str, List[ConversationMessage]],
        model: str = "GPT-4o Mini",
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        """Generate text using specified model."""
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        response = await self.router.generate(messages, model, params)
        return response.text
    
    async def stream(
        self,
        messages: Union[str, List[ConversationMessage]],
        model: str = "GPT-4o Mini",
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ):
        """Stream text generation."""
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
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