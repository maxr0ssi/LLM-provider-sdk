from __future__ import annotations

from typing import Any


def extract_text_from_messages_response(response: Any) -> str:
    """Extract concatenated text from Anthropic messages.create response."""
    text_content = ""
    if hasattr(response, "content") and response.content:
        for content_block in response.content:
            try:
                if getattr(content_block, "type", None) == "text":
                    text_piece = getattr(content_block, "text", "")
                    if text_piece:
                        text_content += text_piece
            except Exception:
                continue
    return text_content


