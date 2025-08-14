from __future__ import annotations

import json
from typing import Any, Optional


def extract_text_from_responses_api(response: Any) -> str:
    """Extract text or JSON string from a Responses API response object.

    Tries output_text first, falls back to first output content item.
    Returns empty string if nothing is found.
    """
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text
    if hasattr(response, "output") and response.output:
        try:
            first = response.output[0]
            if hasattr(first, "content") and first.content:
                part = first.content[0]
                if hasattr(part, "text") and part.text is not None:
                    return part.text
                if hasattr(part, "json") and part.json is not None:
                    return json.dumps(part.json)
        except Exception:
            return ""
    return ""


