"""
Example: Streaming with Usage Data

This example demonstrates how to use the new return_usage parameter
to get token usage and cost information from streaming responses.
"""

import asyncio
from steer_llm_sdk import SteerLLMClient, ConversationMessage, ConversationRole


async def example_basic_streaming_with_usage():
    """Basic example of streaming with usage data."""
    print("=== Basic Streaming with Usage ===\n")
    
    client = SteerLLMClient()
    
    # Enable usage data collection with return_usage=True
    response = await client.stream(
        messages="Write a haiku about Python programming",
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=100,
        return_usage=True
    )
    
    # The response is now a StreamingResponseWithUsage object
    print("Generated text:")
    print(response.get_text())
    print("\nUsage information:")
    print(f"  Prompt tokens: {response.usage['prompt_tokens']}")
    print(f"  Completion tokens: {response.usage['completion_tokens']}")
    print(f"  Total tokens: {response.usage['total_tokens']}")
    
    if response.cost_usd:
        print(f"\nCost: ${response.cost_usd:.6f}")
        if response.cost_breakdown:
            print(f"  Input cost: ${response.cost_breakdown['input_cost']:.6f}")
            print(f"  Output cost: ${response.cost_breakdown['output_cost']:.6f}")
            if response.cost_breakdown.get('cache_savings', 0) > 0:
                print(f"  Cache savings: ${response.cost_breakdown['cache_savings']:.6f}")


async def example_backwards_compatible():
    """Show that the old streaming API still works."""
    print("\n=== Backwards Compatible Streaming ===\n")
    
    client = SteerLLMClient()
    
    print("Streaming chunks as they arrive:")
    chunks = []
    
    # Without return_usage, it works exactly as before
    async for chunk in client.stream(
        messages="Count from 1 to 5",
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=50
    ):
        print(chunk, end='', flush=True)
        chunks.append(chunk)
    
    print("\n\nNo usage data available in this mode")


async def example_conversation_with_usage():
    """Example with conversation messages and usage tracking."""
    print("\n=== Conversation with Usage Tracking ===\n")
    
    client = SteerLLMClient()
    
    messages = [
        ConversationMessage(
            role=ConversationRole.SYSTEM,
            content="You are a helpful coding assistant. Keep responses concise."
        ),
        ConversationMessage(
            role=ConversationRole.USER,
            content="What's the difference between a list and tuple in Python?"
        )
    ]
    
    response = await client.stream(
        messages=messages,
        model="gpt-4o-mini",
        temperature=0.5,
        max_tokens=150,
        return_usage=True
    )
    
    print("Assistant response:")
    print(response.get_text())
    
    print(f"\nTokens used: {response.usage['total_tokens']}")
    print(f"Model: {response.model}")
    print(f"Provider: {response.provider}")
    print(f"Finish reason: {response.finish_reason}")


async def example_cost_tracking():
    """Example showing cost tracking across multiple requests."""
    print("\n=== Cost Tracking Example ===\n")
    
    client = SteerLLMClient()
    total_cost = 0
    total_tokens = 0
    
    prompts = [
        "Write a one-line Python function to reverse a string",
        "Explain list comprehension in one sentence",
        "What's a Python decorator in simple terms?"
    ]
    
    for i, prompt in enumerate(prompts, 1):
        response = await client.stream(
            messages=prompt,
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=100,
            return_usage=True
        )
        
        print(f"{i}. {prompt}")
        print(f"   Response: {response.get_text()}")
        print(f"   Tokens: {response.usage['total_tokens']}")
        
        if response.cost_usd:
            print(f"   Cost: ${response.cost_usd:.6f}")
            total_cost += response.cost_usd
        
        total_tokens += response.usage['total_tokens']
        print()
    
    print(f"Total tokens used: {total_tokens}")
    print(f"Total cost: ${total_cost:.6f}")


async def example_iterate_chunks():
    """Example showing you can still iterate over chunks even with usage data."""
    print("\n=== Iterating Over Chunks ===\n")
    
    client = SteerLLMClient()
    
    response = await client.stream(
        messages="List 3 Python best practices",
        model="gpt-4o-mini",
        temperature=0.5,
        max_tokens=100,
        return_usage=True
    )
    
    # You can iterate over the chunks that were collected
    print("Iterating over collected chunks:")
    for i, chunk in enumerate(response.chunks):
        print(f"Chunk {i}: {repr(chunk)}")
    
    print(f"\nFull text: {response.get_text()}")
    print(f"Total chunks: {len(response.chunks)}")
    print(f"Tokens used: {response.usage['total_tokens']}")


async def main():
    """Run all examples."""
    examples = [
        example_basic_streaming_with_usage,
        example_backwards_compatible,
        example_conversation_with_usage,
        example_cost_tracking,
        example_iterate_chunks
    ]
    
    for example in examples:
        await example()
        print("\n" + "="*50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())