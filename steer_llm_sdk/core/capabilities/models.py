"""
Provider capability models for feature detection and configuration.

Defines what features each provider/model supports to enable
capability-driven behavior instead of hardcoded conditionals.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class ProviderCapabilities(BaseModel):
    """Capabilities supported by a specific provider/model combination."""
    model_config = ConfigDict(extra="forbid")
    
    # Core capabilities
    supports_json_schema: bool = Field(False, description="Native JSON schema support (e.g., OpenAI response_format)")
    supports_streaming: bool = Field(True, description="Streaming response support")
    supports_tools: bool = Field(False, description="Tool/function calling support")
    supports_seed: bool = Field(False, description="Deterministic seed support")
    supports_logprobs: bool = Field(False, description="Log probability support")
    
    # Model limits
    max_context_length: int = Field(..., description="Maximum context window in tokens")
    max_output_tokens: int = Field(..., description="Maximum output tokens")
    
    # API differences
    uses_max_completion_tokens: bool = Field(False, description="Uses max_completion_tokens instead of max_tokens")
    uses_max_output_tokens_in_responses_api: bool = Field(False, description="Uses max_output_tokens in Responses API")
    supports_system_message: bool = Field(True, description="Supports system role in messages")
    supports_response_format: bool = Field(False, description="Supports response_format parameter")
    
    # Caching
    supports_prompt_caching: bool = Field(False, description="Supports prompt caching (e.g., OpenAI, Anthropic)")
    cache_ttl_seconds: Optional[int] = Field(None, description="Cache TTL if supported")
    
    # Cost tracking
    has_input_output_pricing: bool = Field(True, description="Has separate input/output pricing")
    has_cached_pricing: bool = Field(False, description="Has cached token pricing")
    
    # Determinism constraints
    deterministic_temperature_max: float = Field(0.0, description="Max temperature for deterministic mode")
    deterministic_top_p: float = Field(1.0, description="Top-p value for deterministic mode")
    
    # Special behaviors
    supports_temperature: bool = Field(True, description="Supports temperature parameter")
    requires_temperature_one: bool = Field(False, description="Requires temperature=1.0 (e.g., o1 models)")
    supports_multiple_system_messages: bool = Field(False, description="Supports multiple system messages")
    supports_image_inputs: bool = Field(False, description="Supports image inputs")
    
    # Streaming specifics
    streaming_includes_usage: bool = Field(False, description="Usage data available in streaming")
    streaming_delta_format: str = Field("text", description="Format of streaming deltas: text, json, custom")


# Default capabilities for unknown models
DEFAULT_CAPABILITIES = ProviderCapabilities(
    supports_json_schema=False,
    supports_streaming=True,
    supports_tools=False,
    supports_seed=False,
    supports_logprobs=False,
    max_context_length=4096,
    max_output_tokens=4096,
    uses_max_completion_tokens=False,
    uses_max_output_tokens_in_responses_api=False,
    supports_system_message=True,
    supports_response_format=False,
    supports_prompt_caching=False,
    has_input_output_pricing=True,
    has_cached_pricing=False,
    deterministic_temperature_max=0.0,
    deterministic_top_p=1.0,
    supports_temperature=True,
    requires_temperature_one=False,
    supports_multiple_system_messages=False,
    supports_image_inputs=False,
    streaming_includes_usage=False,
    streaming_delta_format="text"
)


# Capability definitions for each model
MODEL_CAPABILITIES: Dict[str, ProviderCapabilities] = {
    # OpenAI models
    "gpt-4o-mini": ProviderCapabilities(
        supports_json_schema=True,
        supports_streaming=True,
        supports_tools=True,
        supports_seed=True,
        supports_logprobs=True,
        max_context_length=128000,
        max_output_tokens=16384,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=True,  # Responses API uses max_output_tokens
        supports_system_message=True,
        supports_response_format=True,
        supports_prompt_caching=True,
        cache_ttl_seconds=300,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        supports_image_inputs=True,
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    "gpt-4.1-nano": ProviderCapabilities(
        supports_json_schema=True,
        supports_streaming=True,
        supports_tools=True,
        supports_seed=True,
        supports_logprobs=False,
        max_context_length=8192,
        max_output_tokens=2048,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=True,  # Responses API uses max_output_tokens
        supports_system_message=True,
        supports_response_format=True,
        supports_prompt_caching=False,
        has_input_output_pricing=True,
        has_cached_pricing=False,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    "gpt-3.5-turbo": ProviderCapabilities(
        supports_json_schema=False,
        supports_streaming=True,
        supports_tools=True,
        supports_seed=True,
        supports_logprobs=False,
        max_context_length=16385,
        max_output_tokens=4096,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=False,
        supports_system_message=True,
        supports_response_format=False,
        supports_prompt_caching=False,
        has_input_output_pricing=True,
        has_cached_pricing=False,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    "o4-mini": ProviderCapabilities(
        supports_json_schema=True,
        supports_streaming=True,
        supports_tools=False,
        supports_seed=False,
        supports_logprobs=False,
        max_context_length=128000,
        max_output_tokens=65536,
        uses_max_completion_tokens=True,  # Uses max_completion_tokens
        uses_max_output_tokens_in_responses_api=True,  # Responses API uses max_output_tokens
        supports_system_message=True,
        supports_response_format=True,
        supports_prompt_caching=True,
        cache_ttl_seconds=300,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=1.0,  # Must use temperature=1.0
        deterministic_top_p=1.0,
        supports_temperature=True,
        requires_temperature_one=True,  # Special requirement
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    "gpt-4.1-mini": ProviderCapabilities(
        supports_json_schema=True,
        supports_streaming=True,
        supports_tools=True,
        supports_seed=True,
        supports_logprobs=True,
        max_context_length=128000,
        max_output_tokens=16384,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=True,  # Responses API uses max_output_tokens
        supports_system_message=True,
        supports_response_format=True,
        supports_prompt_caching=True,
        cache_ttl_seconds=300,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        supports_image_inputs=True,
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    # GPT-5 mini (new model for Nexus)
    "gpt-5-mini": ProviderCapabilities(
        supports_json_schema=True,  # Full Responses API support
        supports_streaming=True,
        supports_tools=True,
        supports_seed=True,
        supports_logprobs=True,
        max_context_length=256000,  # Larger context window
        max_output_tokens=32768,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=True,  # Responses API uses max_output_tokens
        supports_system_message=True,
        supports_response_format=True,  # Native JSON schema
        supports_prompt_caching=True,
        cache_ttl_seconds=600,  # Longer cache
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.1,  # Allows slight variation
        deterministic_top_p=1.0,
        supports_temperature=False,  # GPT-5 mini doesn't support temperature in Responses API
        supports_image_inputs=True,
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    # GPT-4o (flagship)
    "gpt-4o": ProviderCapabilities(
        supports_json_schema=True,
        supports_streaming=True,
        supports_tools=True,
        supports_seed=True,
        supports_logprobs=True,
        max_context_length=128000,
        max_output_tokens=16384,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=True,  # Responses API uses max_output_tokens
        supports_system_message=True,
        supports_response_format=True,
        supports_prompt_caching=True,
        cache_ttl_seconds=300,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        supports_image_inputs=True,
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    # GPT-4.1 (flagship)
    "gpt-4.1": ProviderCapabilities(
        supports_json_schema=True,
        supports_streaming=True,
        supports_tools=True,
        supports_seed=True,
        supports_logprobs=True,
        max_context_length=128000,
        max_output_tokens=16384,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=True,  # Responses API uses max_output_tokens
        supports_system_message=True,
        supports_response_format=True,
        supports_prompt_caching=True,
        cache_ttl_seconds=300,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        supports_image_inputs=True,
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    # GPT-5 (flagship)
    "gpt-5": ProviderCapabilities(
        supports_json_schema=True,
        supports_streaming=True,
        supports_tools=True,
        supports_seed=True,
        supports_logprobs=True,
        max_context_length=512000,  # Even larger context
        max_output_tokens=65536,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=True,  # Responses API uses max_output_tokens
        supports_system_message=True,
        supports_response_format=True,
        supports_prompt_caching=True,
        cache_ttl_seconds=600,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.1,
        deterministic_top_p=1.0,
        supports_temperature=True,
        supports_image_inputs=True,
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    # GPT-5 nano
    "gpt-5-nano": ProviderCapabilities(
        supports_json_schema=True,
        supports_streaming=True,
        supports_tools=True,
        supports_seed=True,
        supports_logprobs=False,
        max_context_length=16384,
        max_output_tokens=4096,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=True,  # Responses API uses max_output_tokens
        supports_system_message=True,
        supports_response_format=True,
        supports_prompt_caching=True,
        cache_ttl_seconds=300,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        streaming_includes_usage=True,
        streaming_delta_format="text"
    ),
    
    # Anthropic models
    "claude-3-haiku-20240307": ProviderCapabilities(
        supports_json_schema=False,  # No native JSON schema
        supports_streaming=True,
        supports_tools=False,
        supports_seed=False,
        supports_logprobs=False,
        max_context_length=200000,
        max_output_tokens=4096,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=False,
        supports_system_message=True,
        supports_response_format=False,
        supports_prompt_caching=True,
        cache_ttl_seconds=300,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        supports_multiple_system_messages=True,
        streaming_includes_usage=False,  # No usage in streaming
        streaming_delta_format="text"
    ),
    
    "claude-3-5-sonnet-20241022": ProviderCapabilities(
        supports_json_schema=False,
        supports_streaming=True,
        supports_tools=True,  # Anthropic has tool support
        supports_seed=False,
        supports_logprobs=False,
        max_context_length=200000,
        max_output_tokens=8192,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=False,
        supports_system_message=True,
        supports_response_format=False,
        supports_prompt_caching=True,
        cache_ttl_seconds=300,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        supports_multiple_system_messages=True,
        supports_image_inputs=True,
        streaming_includes_usage=False,
        streaming_delta_format="text"
    ),
    
    "claude-3-opus-20240229": ProviderCapabilities(
        supports_json_schema=False,
        supports_streaming=True,
        supports_tools=True,
        supports_seed=False,
        supports_logprobs=False,
        max_context_length=200000,
        max_output_tokens=4096,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=False,
        supports_system_message=True,
        supports_response_format=False,
        supports_prompt_caching=True,
        cache_ttl_seconds=300,
        has_input_output_pricing=True,
        has_cached_pricing=True,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        supports_multiple_system_messages=True,
        supports_image_inputs=True,
        streaming_includes_usage=False,
        streaming_delta_format="text"
    ),
    
    # xAI models
    "grok-beta": ProviderCapabilities(
        supports_json_schema=False,
        supports_streaming=True,
        supports_tools=False,
        supports_seed=False,
        supports_logprobs=False,
        max_context_length=131072,
        max_output_tokens=4096,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=False,
        supports_system_message=True,
        supports_response_format=False,
        supports_prompt_caching=False,
        has_input_output_pricing=True,
        has_cached_pricing=False,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        streaming_includes_usage=False,
        streaming_delta_format="text"
    ),
    
    "grok-2-1212": ProviderCapabilities(
        supports_json_schema=False,
        supports_streaming=True,
        supports_tools=False,
        supports_seed=False,
        supports_logprobs=False,
        max_context_length=131072,
        max_output_tokens=4096,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=False,
        supports_system_message=True,
        supports_response_format=False,
        supports_prompt_caching=False,
        has_input_output_pricing=True,
        has_cached_pricing=False,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        streaming_includes_usage=False,
        streaming_delta_format="text"
    ),
    
    "grok-3-mini": ProviderCapabilities(
        supports_json_schema=False,
        supports_streaming=True,
        supports_tools=False,
        supports_seed=False,
        supports_logprobs=False,
        max_context_length=131072,
        max_output_tokens=8192,
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=False,
        supports_system_message=True,
        supports_response_format=False,
        supports_prompt_caching=False,
        has_input_output_pricing=True,
        has_cached_pricing=False,
        deterministic_temperature_max=0.0,
        deterministic_top_p=1.0,
        supports_temperature=True,
        streaming_includes_usage=False,
        streaming_delta_format="text"
    ),
}

# Add versioned model aliases that point to the same capabilities
MODEL_CAPABILITIES["o4-mini-2025-04-16"] = MODEL_CAPABILITIES["o4-mini"]
MODEL_CAPABILITIES["gpt-4.1-mini-2025-04-14"] = MODEL_CAPABILITIES["gpt-4.1-mini"]
MODEL_CAPABILITIES["claude-3-5-haiku-20241022"] = ProviderCapabilities(
    supports_json_schema=False,
    supports_streaming=True,
    supports_tools=False,
    supports_seed=False,
    supports_logprobs=False,
    max_context_length=200000,
    max_output_tokens=8192,
    uses_max_completion_tokens=False,
    uses_max_output_tokens_in_responses_api=False,
    supports_system_message=True,
    supports_response_format=False,
    supports_prompt_caching=True,
    cache_ttl_seconds=300,
    has_input_output_pricing=True,
    has_cached_pricing=True,
    deterministic_temperature_max=0.0,
    deterministic_top_p=1.0,
    supports_temperature=True,
    supports_multiple_system_messages=True,
    streaming_includes_usage=False,
    streaming_delta_format="text"
)


def get_model_capabilities(model_id: str) -> ProviderCapabilities:
    """Get capabilities for a specific model, with fallback to defaults."""
    return MODEL_CAPABILITIES.get(model_id, DEFAULT_CAPABILITIES)