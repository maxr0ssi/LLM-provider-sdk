from __future__ import annotations

import inspect
from typing import Any, AsyncGenerator

from ...streaming import StreamAdapter


async def stream_chat(chat: Any, adapter: StreamAdapter) -> AsyncGenerator[str, None]:
    """Iterate xAI chat.stream(), handling coroutine or async-iterator return.
    Yields normalized text chunks via StreamAdapter.
    """
    stream_iter = chat.stream()
    if inspect.iscoroutine(stream_iter):
        stream_iter = await stream_iter

    async for response, chunk in stream_iter:
        delta = adapter.normalize_delta((response, chunk))
        text = delta.get_text()
        if text:
            adapter.track_chunk(len(text))
            yield text


async def stream_chat_with_usage(chat: Any, adapter: StreamAdapter, prompt_text: str) -> AsyncGenerator[tuple, None]:
    """Stream xAI chat and emit (text, None) tuples and final (None, usage)."""
    collected = []
    finish_reason = None

    stream_iter = chat.stream()
    if inspect.iscoroutine(stream_iter):
        stream_iter = await stream_iter

    async for response, chunk in stream_iter:
        delta = adapter.normalize_delta((response, chunk))
        text = delta.get_text()
        if text:
            adapter.track_chunk(len(text))
            collected.append(text)
            yield (text, None)
        if hasattr(response, 'choices') and response.choices:
            if hasattr(response.choices[0], 'finish_reason'):
                finish_reason = response.choices[0].finish_reason

    full_text = ''.join(collected)
    prompt_tokens = len(prompt_text) // 4
    completion_tokens = len(full_text) // 4
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cache_info": {}
    }
    yield (None, {
        "usage": usage,
        "model": None,
        "provider": "xai",
        "finish_reason": finish_reason or "stop",
        "cost_usd": None,
        "cost_breakdown": None
    })
