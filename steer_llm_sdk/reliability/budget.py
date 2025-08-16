from __future__ import annotations

from typing import Any, Dict


def clamp_params_to_budget(params: Dict[str, Any], budget: Dict[str, Any] | None) -> Dict[str, Any]:
    if not budget or not isinstance(budget, dict):
        return params
    result = dict(params)
    if "tokens" in budget:
        try:
            max_tokens_budget = int(budget["tokens"])
            existing = int(result.get("max_tokens", max_tokens_budget))
            result["max_tokens"] = min(existing, max_tokens_budget)
        except Exception:
            pass
    return result


