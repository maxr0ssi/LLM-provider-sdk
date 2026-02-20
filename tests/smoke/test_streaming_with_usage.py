"""Test streaming responses with usage data."""

import asyncio
import os
import pytest
from steer_llm_sdk import SteerLLMClient, ConversationMessage, ConversationRole


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY")
@pytest.mark.asyncio
async def test_stream_with_usage_openai():
    """Test streaming with usage data for OpenAI."""
    client = SteerLLMClient()
    
    # Test with return_usage=True
    response = await client.stream_with_usage(
        messages="Tell me a joke about programming in 10 words or less",
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=50,
    )
    
    # Check that we got a StreamingResponseWithUsage object
    assert hasattr(response, 'usage')
    assert hasattr(response, 'get_text')
    assert hasattr(response, 'chunks')
    
    # Get the full text
    full_text = response.get_text()
    assert len(full_text) > 0
    
    # Check usage data
    assert response.usage is not None
    assert 'prompt_tokens' in response.usage
    assert 'completion_tokens' in response.usage
    assert 'total_tokens' in response.usage
    assert response.usage['total_tokens'] == response.usage['prompt_tokens'] + response.usage['completion_tokens']
    
    # Check other metadata
    assert response.model is not None
    assert response.provider == 'openai'
    assert response.finish_reason is not None
    
    print(f"Full text: {full_text}")
    print(f"Usage: {response.usage}")
    print(f"Cost: ${response.cost_usd:.6f}" if response.cost_usd else "Cost: N/A")


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY")
@pytest.mark.asyncio
async def test_stream_backwards_compatible():
    """Test that streaming without return_usage works as before."""
    client = SteerLLMClient()
    
    chunks = []
    # Old style - should work exactly as before
    async for chunk in client.stream(
        messages="Count to 5",
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=50
    ):
        chunks.append(chunk)
    
    # Should have received string chunks
    assert len(chunks) > 0
    assert all(isinstance(chunk, str) for chunk in chunks)
    
    full_text = ''.join(chunks)
    assert len(full_text) > 0
    print(f"Backwards compatible streaming result: {full_text}")


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="Requires ANTHROPIC_API_KEY")
@pytest.mark.asyncio
async def test_stream_with_usage_anthropic():
    """Test streaming with usage data for Anthropic."""
    client = SteerLLMClient()
    
    messages = [
        ConversationMessage(role=ConversationRole.SYSTEM, content="You are a helpful assistant."),
        ConversationMessage(role=ConversationRole.USER, content="Say 'Hello, World!' and nothing else.")
    ]
    
    # Test with return_usage=True
    response = await client.stream_with_usage(
        messages=messages,
        model="claude-3-5-haiku-20241022",
        temperature=0,
        max_tokens=50
    )
    
    # Check response structure
    assert hasattr(response, 'usage')
    assert hasattr(response, 'get_text')
    
    # Get the full text
    full_text = response.get_text()
    assert "Hello, World!" in full_text
    
    # Check usage data
    assert response.usage is not None
    assert response.usage['prompt_tokens'] > 0
    assert response.usage['completion_tokens'] > 0
    
    # Check provider-specific data
    assert response.provider == 'anthropic'
    
    print(f"Anthropic response: {full_text}")
    print(f"Anthropic usage: {response.usage}")


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY")
@pytest.mark.asyncio
async def test_stream_with_usage_json_format():
    """Test streaming with JSON response format and usage data."""
    client = SteerLLMClient()
    
    response = await client.stream_with_usage(
        messages="Return a JSON object with a 'joke' field containing a programming joke",
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=100,
        response_format={"type": "json_object"}
    )
    
    # Get full response
    full_text = response.get_text()
    
    # Should be valid JSON
    import json
    parsed = json.loads(full_text)
    assert 'joke' in parsed
    
    # Check usage data is still available
    assert response.usage is not None
    assert response.usage['total_tokens'] > 0
    
    print(f"JSON response: {parsed}")
    print(f"Token usage: {response.usage}")


async def main():
    """Run all tests."""
    print("Testing streaming with usage data...\n")
    
    print("1. Testing OpenAI streaming with usage...")
    try:
        await test_stream_with_usage_openai()
        print("✅ OpenAI test passed\n")
    except Exception as e:
        print(f"❌ OpenAI test failed: {e}\n")
    
    print("2. Testing backwards compatibility...")
    try:
        await test_stream_backwards_compatible()
        print("✅ Backwards compatibility test passed\n")
    except Exception as e:
        print(f"❌ Backwards compatibility test failed: {e}\n")
    
    print("3. Testing Anthropic streaming with usage...")
    try:
        await test_stream_with_usage_anthropic()
        print("✅ Anthropic test passed\n")
    except Exception as e:
        print(f"❌ Anthropic test failed: {e}\n")
    
    print("4. Testing JSON format with usage...")
    try:
        await test_stream_with_usage_json_format()
        print("✅ JSON format test passed\n")
    except Exception as e:
        print(f"❌ JSON format test failed: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())