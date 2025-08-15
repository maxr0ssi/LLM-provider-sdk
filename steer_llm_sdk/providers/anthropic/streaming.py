from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from ...streaming import StreamAdapter


async def stream_messages(
    client: Any,
    params: Dict[str, Any],
    adapter: StreamAdapter,
) -> AsyncGenerator[str, None]:
    """Stream Anthropic messages.create and yield normalized text chunks."""
    stream = await client.messages.create(**params)
    async for event in stream:
        delta = adapter.normalize_delta(event)
        text = delta.get_text()
        if text:
            await adapter.track_chunk(len(text), text)
            yield text


async def stream_messages_with_usage(
    client: Any,
    params: Dict[str, Any],
    adapter: StreamAdapter,
) -> AsyncGenerator[tuple, None]:
    """Stream Anthropic messages with usage, emitting (text, None) and final (None, usage)."""
    stream = await client.messages.create(**params)
    collected_chunks = []
    finish_reason = None
    usage_data = None

    async for event in stream:
        delta = adapter.normalize_delta(event)
        text = delta.get_text()
        if text:
            await adapter.track_chunk(len(text), text)
            collected_chunks.append(text)
            yield (text, None)

        if getattr(event, "type", None) == "message_delta":
            if hasattr(event, "usage"):
                usage_data = event.usage
            if hasattr(event, "delta") and hasattr(event.delta, "stop_reason"):
                finish_reason = event.delta.stop_reason
        elif adapter.should_emit_usage(event):
            if usage_data:
                usage_dict = usage_data.model_dump() if hasattr(usage_data, "model_dump") else usage_data.__dict__
                yield (
                    None,
                    {
                        "usage": usage_dict,
                        "model": params.get("model"),
                        "provider": "anthropic",
                        "finish_reason": finish_reason,
                        "cost_usd": None,
                        "cost_breakdown": None,
                    },
                )


