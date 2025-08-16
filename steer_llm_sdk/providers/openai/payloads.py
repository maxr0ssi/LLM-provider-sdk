from typing import Any, Dict, Optional, List

from ...models.generation import GenerationParams
from ...core.capabilities import get_cache_control_config


def build_responses_api_payload(
    params: GenerationParams,
    openai_params: dict,
    transformed_messages: Any,
    text_config: Optional[dict] = None,
) -> dict:
    """Build payload for OpenAI Responses API.

    Copies only Responses API-compatible parameters and maps max tokens
    appropriately. This mirrors the previous adapter-local implementation.
    """
    responses_payload: Dict[str, Any] = {
        "model": params.model,
    }

    # Add transformed messages (either as input or instructions+messages)
    if isinstance(transformed_messages, dict):
        responses_payload.update(transformed_messages)
    else:
        responses_payload["input"] = transformed_messages

    # Copy only Responses API compatible parameters
    # Responses API accepts: temperature, top_p, max_output_tokens, seed, stop
    responses_api_params = ["temperature", "top_p", "seed", "stop"]
    for key in responses_api_params:
        if key in openai_params and openai_params[key] is not None:
            responses_payload[key] = openai_params[key]

    # Handle max tokens mapping
    if "max_completion_tokens" in openai_params:
        responses_payload["max_output_tokens"] = openai_params["max_completion_tokens"]
    elif "max_tokens" in openai_params:
        responses_payload["max_output_tokens"] = openai_params["max_tokens"]

    if text_config is not None:
        responses_payload["text"] = text_config

    # Optional: reasoning and metadata pass-through if provided
    if hasattr(params, "reasoning") and getattr(params, "reasoning") is not None:
        responses_payload["reasoning"] = getattr(params, "reasoning")
    if hasattr(params, "metadata") and getattr(params, "metadata") is not None:
        responses_payload["metadata"] = getattr(params, "metadata")

    return responses_payload


def apply_prompt_cache_control(
    caps: Any,
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Inject provider-specific cache_control for long system messages.

    For OpenAI, if the first message is a system message and exceeds the
    threshold, attach an ephemeral cache_control block via capability helper.
    """
    if messages and messages[0].get("role") == "system":
        system_content = messages[0].get("content", "")
        try:
            length = len(system_content) if isinstance(system_content, str) else 0
        except Exception:
            length = 0
        cache_config = get_cache_control_config(caps, "openai", length)
        if cache_config:
            messages[0]["cache_control"] = cache_config
    return messages


