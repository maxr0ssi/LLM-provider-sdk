"""
Unit tests for provider capabilities.
"""

import pytest

from steer_llm_sdk.core.capabilities.models import (
    ProviderCapabilities,
    DEFAULT_CAPABILITIES,
    MODEL_CAPABILITIES,
    get_model_capabilities
)


class TestProviderCapabilities:
    """Test ProviderCapabilities model."""
    
    def test_default_capabilities(self):
        """Test default capability values."""
        caps = DEFAULT_CAPABILITIES
        assert caps.supports_json_schema is False
        assert caps.supports_streaming is True
        assert caps.supports_tools is False
        assert caps.supports_seed is False
        assert caps.max_context_length == 4096
        assert caps.max_output_tokens == 4096
        assert caps.deterministic_temperature_max == 0.0
        assert caps.streaming_delta_format == "text"
    
    def test_gpt5_mini_capabilities(self):
        """Test GPT-5 mini has expected capabilities."""
        caps = MODEL_CAPABILITIES["gpt-5-mini"]
        assert caps.supports_json_schema is True  # Full Responses API
        assert caps.supports_streaming is True
        assert caps.supports_tools is True
        assert caps.supports_seed is True
        assert caps.max_context_length == 256000  # 256K context
        assert caps.max_output_tokens == 32768
        assert caps.supports_response_format is True
        assert caps.supports_prompt_caching is True
        assert caps.cache_ttl_seconds == 600
        assert caps.deterministic_temperature_max == 0.1
    
    def test_gpt4o_mini_capabilities(self):
        """Test GPT-4o mini capabilities."""
        caps = MODEL_CAPABILITIES["gpt-4o-mini"]
        assert caps.supports_json_schema is True
        assert caps.supports_tools is True
        assert caps.supports_seed is True
        assert caps.supports_prompt_caching is True
        assert caps.has_cached_pricing is True
        assert caps.supports_image_inputs is True
        assert caps.streaming_includes_usage is True
    
    def test_o4_mini_special_capabilities(self):
        """Test o4-mini special requirements."""
        caps = MODEL_CAPABILITIES["o4-mini"]
        assert caps.uses_max_completion_tokens is True  # Special field name
        assert caps.requires_temperature_one is True  # Must be 1.0
        assert caps.deterministic_temperature_max == 1.0
        assert caps.supports_tools is False  # No tool support
        assert caps.supports_seed is False
    
    def test_anthropic_capabilities(self):
        """Test Anthropic model capabilities."""
        # Claude 3 Haiku
        haiku = MODEL_CAPABILITIES["claude-3-haiku-20240307"]
        assert haiku.supports_json_schema is False  # No native JSON schema
        assert haiku.supports_streaming is True
        assert haiku.supports_tools is False
        assert haiku.supports_multiple_system_messages is True
        assert haiku.streaming_includes_usage is False
        assert haiku.supports_prompt_caching is True
        
        # Claude 3.5 Sonnet
        sonnet = MODEL_CAPABILITIES["claude-3-5-sonnet-20241022"]
        assert sonnet.supports_tools is True  # Has tool support
        assert sonnet.supports_image_inputs is True
        assert sonnet.max_context_length == 200000
    
    def test_xai_capabilities(self):
        """Test xAI model capabilities."""
        grok = MODEL_CAPABILITIES["grok-beta"]
        assert grok.supports_json_schema is False
        assert grok.supports_streaming is True
        assert grok.supports_tools is False
        assert grok.supports_prompt_caching is False
        assert grok.max_context_length == 131072
        
        grok3 = MODEL_CAPABILITIES["grok-3-mini"]
        assert grok3.max_output_tokens == 8192
    
    def test_capability_fields(self):
        """Test all capability fields are properly defined."""
        caps = ProviderCapabilities(
            supports_json_schema=True,
            supports_streaming=True,
            supports_tools=True,
            supports_seed=True,
            supports_logprobs=True,
            max_context_length=128000,
            max_output_tokens=8192,
            uses_max_completion_tokens=True,
            supports_system_message=True,
            supports_response_format=True,
            supports_prompt_caching=True,
            cache_ttl_seconds=300,
            has_input_output_pricing=True,
            has_cached_pricing=True,
            deterministic_temperature_max=0.1,
            deterministic_top_p=1.0,
            requires_temperature_one=False,
            supports_multiple_system_messages=True,
            supports_image_inputs=True,
            streaming_includes_usage=True,
            streaming_delta_format="json"
        )
        
        # Verify all fields
        assert caps.supports_json_schema is True
        assert caps.cache_ttl_seconds == 300
        assert caps.streaming_delta_format == "json"
    
    def test_get_model_capabilities(self):
        """Test getting capabilities by model ID."""
        # Known model
        caps = get_model_capabilities("gpt-5-mini")
        assert caps.supports_json_schema is True
        assert caps.max_context_length == 256000
        
        # Unknown model falls back to defaults
        caps = get_model_capabilities("unknown-model")
        assert caps == DEFAULT_CAPABILITIES
        assert caps.supports_json_schema is False
        assert caps.max_context_length == 4096
    
    def test_no_extra_fields(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(Exception):  # Pydantic validation
            ProviderCapabilities(
                supports_json_schema=True,
                supports_streaming=True,
                max_context_length=4096,
                max_output_tokens=4096,
                extra_field="not allowed"
            )