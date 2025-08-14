from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...config.models import MODEL_CONFIGS


@dataclass
class ProviderCapabilities:
    supports_json_schema: bool
    supports_streaming: bool
    supports_seed: bool
    supports_tools: bool
    supports_logprobs: bool
    supports_temperature: bool
    uses_max_completion_tokens: bool
    max_context_length: Optional[int] = None
    max_output_tokens: Optional[int] = None
    fixed_temperature: Optional[float] = None


def get_capabilities_for_model(model_identifier: str) -> ProviderCapabilities:
    """Return capabilities for a given model id derived from model config and known provider features.

    This is a minimal registry; expand per provider as needed.
    """
    # Accept either the registry key (e.g., "gpt-4.1-mini") or the provider model id (e.g., "gpt-4.1-mini-2025-04-14")
    config = MODEL_CONFIGS.get(model_identifier)
    if not config:
        # Fallback: search by llm_model_id or display fields
        for key, cfg in MODEL_CONFIGS.items():
            if isinstance(cfg, dict):
                if cfg.get("llm_model_id") == model_identifier or cfg.get("name") == model_identifier or cfg.get("display_name") == model_identifier:
                    config = cfg
                    break
    provider = (config or {}).get("provider", "") if isinstance(config, dict) else getattr(config, "provider", "")
    model_name = (model_identifier or "").lower()

    # Defaults (conservative)
    caps = ProviderCapabilities(
        supports_json_schema=False,
        supports_streaming=True,
        supports_seed=True,
        supports_tools=False,
        supports_logprobs=False,
        supports_temperature=True,
        uses_max_completion_tokens=False,
        max_context_length=getattr(config, "context_length", None) if config else None,
        max_output_tokens=getattr(config, "max_tokens", None) if config else None,
    )

    if provider == "openai":
        # Responses API native structured output for modern OpenAI models
        if "gpt-5-mini" in model_name or "gpt-4.1-mini" in model_name:
            caps.supports_json_schema = True
            caps.uses_max_completion_tokens = True
            if "gpt-5-mini" in model_name:
                caps.supports_temperature = False
        elif model_name == "o4-mini" or model_name.startswith("o4-mini-"):
            caps.supports_json_schema = False
            caps.uses_max_completion_tokens = True
            caps.fixed_temperature = 1.0
        else:
            # legacy chat completions path
            caps.supports_json_schema = False
            caps.uses_max_completion_tokens = False

    elif provider == "anthropic":
        # Anthropic messages API; no native JSON schema
        caps.supports_json_schema = False
        caps.uses_max_completion_tokens = False
        caps.supports_seed = True

    elif provider == "xai":
        # xAI SDK specifics unknown for schema/seed; keep conservative
        caps.supports_json_schema = False
        caps.supports_seed = False
        caps.uses_max_completion_tokens = False

    return caps


