from __future__ import annotations

from typing import Any, Dict


class StreamAdapter:
    def normalize_delta(self, provider_delta: Any) -> Dict[str, Any]:
        # Attempt JSON; fallback to text
        if isinstance(provider_delta, (dict, list)):
            return {"type": "json", "value": provider_delta}
        # Some providers pass small event objects with .delta/.text
        text = None
        if hasattr(provider_delta, "delta"):
            text = getattr(provider_delta, "delta")
        if hasattr(provider_delta, "text") and not text:
            text = getattr(provider_delta, "text")
        return {"type": "text", "value": str(text if text is not None else provider_delta)}


