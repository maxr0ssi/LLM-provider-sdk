from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from ...streaming import StreamAdapter


async def stream_responses_api(
    client: Any,
    payload: Dict[str, Any],
    adapter: StreamAdapter,
) -> AsyncGenerator[str, None]:
    """Stream from OpenAI Responses API yielding only incremental deltas as text."""
    stream = await client.responses.create(**payload)
    async for event in stream:
        piece = getattr(event, "delta", None)
        if piece:
            yield str(piece)


async def stream_responses_api_with_usage(
    client: Any,
    payload: Dict[str, Any],
    adapter: StreamAdapter,
) -> AsyncGenerator[tuple, None]:
    """Stream from OpenAI Responses API yielding incremental deltas and a final usage tuple.

    Note: The API may not include usage in-stream; we emit a final (None, usage_dict) with zeros.
    """
    collected = []
    stream = await client.responses.create(**payload)
    async for event in stream:
        piece = getattr(event, "delta", None)
        if piece:
            text = str(piece)
            collected.append(text)
            yield (text, None)
    # Final usage placeholder (provider variance)
    yield (
        None,
        {
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cache_info": {},
            },
            "model": payload.get("model"),
            "provider": "openai",
            "finish_reason": None,
            "cost_usd": None,
            "cost_breakdown": None,
        },
    )


