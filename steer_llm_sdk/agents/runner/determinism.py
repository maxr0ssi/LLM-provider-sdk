from __future__ import annotations

from typing import Any, Dict

from ...llm.capabilities import get_capabilities_for_model


def apply_deterministic_policy(params: Dict[str, Any], model_id: str) -> Dict[str, Any]:
    """Clamp parameters for deterministic runs and propagate seed when supported.

    Returns a shallow copy with safe values applied.
    """
    safe = dict(params)
    caps = get_capabilities_for_model(model_id)

    # Clamp sampling
    if "temperature" in safe:
        safe["temperature"] = 0.0
    if "top_p" in safe and safe.get("top_p") is not None:
        safe["top_p"] = min(0.1, float(safe["top_p"]))

    # Only include seed if supported
    if not caps.supports_seed and "seed" in safe:
        safe.pop("seed", None)

    return safe


