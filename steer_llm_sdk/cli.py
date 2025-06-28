"""CLI entry point for Steer LLM SDK."""

import argparse
import asyncio
import json
from typing import Optional

from .main import SteerLLMClient
from .models.conversation_types import ConversationMessage, TurnRole


async def generate_text(model: str, prompt: str, max_tokens: Optional[int] = None, 
                       temperature: Optional[float] = None, stream: bool = False):
    """Generate text using the specified model."""
    client = SteerLLMClient()
    
    params = {}
    if max_tokens:
        params['max_tokens'] = max_tokens
    if temperature is not None:
        params['temperature'] = temperature
    
    try:
        if stream:
            print(f"Streaming response from {model}:\n")
            async for chunk in client.generate_stream(prompt, model, params):
                print(chunk, end='', flush=True)
            print()  # New line at the end
        else:
            result = await client.generate(prompt, model, params)
            print(f"Response from {model}:\n")
            print(result.text)
            print(f"\nTokens used: {result.usage}")
    except Exception as e:
        print(f"Error: {str(e)}")


async def list_models():
    """List all available models."""
    client = SteerLLMClient()
    models = await client.get_available_models()
    
    print("Available Models:")
    print("-" * 50)
    for model in models:
        status = "✓" if model.available else "✗"
        print(f"{status} {model.name} ({model.provider})")
        print(f"   {model.description}")
        if model.cost_per_1k_tokens:
            print(f"   Cost: ${model.cost_per_1k_tokens}/1k tokens")
        print()


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="Steer LLM SDK CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate text using an LLM')
    generate_parser.add_argument('model', help='Model name (e.g., "GPT-4o Mini")')
    generate_parser.add_argument('prompt', help='Text prompt')
    generate_parser.add_argument('--max-tokens', type=int, help='Maximum tokens to generate')
    generate_parser.add_argument('--temperature', type=float, help='Temperature (0.0-2.0)')
    generate_parser.add_argument('--stream', action='store_true', help='Stream the response')
    
    # List models command
    list_parser = subparsers.add_parser('list-models', help='List available models')
    
    args = parser.parse_args()
    
    if args.command == 'generate':
        asyncio.run(generate_text(
            args.model, 
            args.prompt, 
            args.max_tokens, 
            args.temperature,
            args.stream
        ))
    elif args.command == 'list-models':
        asyncio.run(list_models())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()