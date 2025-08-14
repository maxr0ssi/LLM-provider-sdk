from __future__ import annotations

from typing import Any, Dict
from ...core.capabilities import get_cache_control_config


def assemble_messages_params(base_params: Dict[str, Any], transformed: Any) -> Dict[str, Any]:
    """Merge transformed Anthropic messages/system structure into params.

    Drops system=None to satisfy SDK validators; preserves dict-structured
    system blocks when provided.
    """
    params = dict(base_params)
    if isinstance(transformed, dict):
        params.update(transformed)
        if params.get("system") is None:
            params.pop("system", None)
    else:
        params["messages"] = transformed
    return params


def apply_system_cache_control(
    caps: Any,
    params: Dict[str, Any],
    system_message: str | None,
) -> Dict[str, Any]:
    """Inject Anthropic cache_control for long system messages.

    If `system_message` is provided as a string, this will either wrap it
    into the Anthropic block format with cache_control or set it as a plain
    system string when below threshold.
    """
    if not system_message:
        return params

    cache_config = get_cache_control_config(caps, "anthropic", len(system_message))
    updated = dict(params)
    if cache_config:
        updated["system"] = [
            {
                "type": "text",
                "text": system_message,
                "cache_control": cache_config,
            }
        ]
    else:
        updated["system"] = system_message
    return updated


