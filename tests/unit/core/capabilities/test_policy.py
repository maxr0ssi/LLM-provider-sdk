"""Tests for capability-driven policy helpers."""

import pytest
from steer_llm_sdk.core.capabilities import (
    ProviderCapabilities,
    map_max_tokens_field,
    apply_temperature_policy,
    format_responses_api_schema,
    should_use_responses_api,
    get_deterministic_settings,
    supports_prompt_caching,
    get_cache_control_config
)


class TestMaxTokensMapping:
    """Test max tokens field mapping based on capabilities."""
    
    def test_standard_max_tokens(self):
        """Test standard max_tokens field for most models."""
        caps = ProviderCapabilities(
            max_context_length=4096,
            max_output_tokens=4096,
            uses_max_completion_tokens=False,
            uses_max_output_tokens_in_responses_api=False
        )
        assert map_max_tokens_field(caps, "openai") == "max_tokens"
    
    def test_max_completion_tokens(self):
        """Test models that use max_completion_tokens (e.g., o4-mini)."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=65536,
            uses_max_completion_tokens=True,
            uses_max_output_tokens_in_responses_api=True
        )
        assert map_max_tokens_field(caps, "openai") == "max_completion_tokens"
    
    def test_responses_api_max_output_tokens(self):
        """Test Responses API uses max_output_tokens."""
        caps = ProviderCapabilities(
            max_context_length=256000,
            max_output_tokens=32768,
            uses_max_completion_tokens=False,
            uses_max_output_tokens_in_responses_api=True
        )
        assert map_max_tokens_field(caps, "openai", use_responses_api=True) == "max_output_tokens"


class TestTemperaturePolicy:
    """Test temperature policy application based on capabilities."""
    
    def test_temperature_not_supported(self):
        """Test temperature removal for models that don't support it."""
        caps = ProviderCapabilities(
            max_context_length=256000,
            max_output_tokens=32768,
            supports_temperature=False  # e.g., gpt-5-mini in Responses API
        )
        params = {"temperature": 0.7, "top_p": 0.9}
        result = apply_temperature_policy(params, caps)
        assert "temperature" not in result
        assert result["top_p"] == 0.9
    
    def test_temperature_required_one(self):
        """Test temperature forced to 1.0 for models that require it."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=65536,
            supports_temperature=True,
            requires_temperature_one=True  # e.g., o4-mini
        )
        params = {"temperature": 0.5}
        result = apply_temperature_policy(params, caps)
        assert result["temperature"] == 1.0
    
    def test_temperature_deterministic_clamping(self):
        """Test temperature clamping for deterministic mode."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=16384,
            supports_temperature=True,
            deterministic_temperature_max=0.1
        )
        params = {"temperature": 0.9}
        result = apply_temperature_policy(params, caps)
        assert result["temperature"] == 0.1
    
    def test_temperature_normal_passthrough(self):
        """Test normal temperature passthrough when supported."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=16384,
            supports_temperature=True,
            deterministic_temperature_max=1.0
        )
        params = {"temperature": 0.7}
        result = apply_temperature_policy(params, caps)
        assert result["temperature"] == 0.7


class TestResponsesAPISchema:
    """Test Responses API schema formatting."""
    
    def test_basic_schema_formatting(self):
        """Test basic schema formatting with additionalProperties."""
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"}
            },
            "required": ["answer"]
        }
        result = format_responses_api_schema(schema, "test_schema")
        
        assert result == {
            "format": {
                "type": "json_schema",
                "name": "test_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"}
                    },
                    "required": ["answer"],
                    "additionalProperties": False
                }
            }
        }
    
    def test_schema_with_strict(self):
        """Test schema formatting with strict mode."""
        schema = {"type": "object", "properties": {}}
        result = format_responses_api_schema(schema, "strict_schema", strict=True)
        
        assert result["format"]["strict"] is True
        assert result["format"]["schema"]["additionalProperties"] is False
    
    def test_schema_preserves_existing_additional_properties(self):
        """Test that existing additionalProperties is preserved."""
        schema = {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "additionalProperties": True
        }
        result = format_responses_api_schema(schema, "flexible_schema")
        
        # Should preserve the original value
        assert result["format"]["schema"]["additionalProperties"] is True


class TestResponsesAPIDetection:
    """Test Responses API usage detection."""
    
    def test_should_use_responses_api_with_schema(self):
        """Test detection when schema is provided and supported."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=16384,
            supports_json_schema=True
        )
        params = {
            "response_format": {
                "json_schema": {"type": "object"},
                "name": "test"
            }
        }
        assert should_use_responses_api(params, caps) is True
    
    def test_should_not_use_responses_api_no_schema_support(self):
        """Test no Responses API when model doesn't support schemas."""
        caps = ProviderCapabilities(
            max_context_length=200000,
            max_output_tokens=4096,
            supports_json_schema=False
        )
        params = {
            "response_format": {
                "json_schema": {"type": "object"}
            }
        }
        assert should_use_responses_api(params, caps) is False
    
    def test_should_not_use_responses_api_no_schema_requested(self):
        """Test no Responses API when no schema is requested."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=16384,
            supports_json_schema=True
        )
        params = {"response_format": {"type": "json_object"}}
        assert should_use_responses_api(params, caps) is False


class TestDeterministicSettings:
    """Test deterministic settings based on capabilities."""
    
    def test_deterministic_with_seed_support(self):
        """Test deterministic settings with seed support."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=16384,
            supports_seed=True,
            deterministic_temperature_max=0.0,
            deterministic_top_p=1.0
        )
        result = get_deterministic_settings(caps, deterministic=True)
        
        assert result["temperature"] == 0.0
        assert result["top_p"] == 1.0
        assert result["seed"] == 42
    
    def test_deterministic_temperature_one_required(self):
        """Test deterministic with temperature=1.0 requirement."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=65536,
            requires_temperature_one=True,
            deterministic_top_p=1.0
        )
        result = get_deterministic_settings(caps, deterministic=True)
        
        assert result["temperature"] == 1.0
        assert result["top_p"] == 1.0
    
    def test_non_deterministic_returns_empty(self):
        """Test non-deterministic mode returns empty dict."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=16384
        )
        result = get_deterministic_settings(caps, deterministic=False)
        assert result == {}


class TestPromptCaching:
    """Test prompt caching policy."""
    
    def test_caching_supported(self):
        """Test when caching is supported."""
        caps = ProviderCapabilities(
            max_context_length=128000,
            max_output_tokens=16384,
            supports_prompt_caching=True,
            cache_ttl_seconds=300
        )
        assert supports_prompt_caching(caps, "openai") is True
    
    def test_caching_not_supported(self):
        """Test when caching is not supported."""
        caps = ProviderCapabilities(
            max_context_length=131072,
            max_output_tokens=4096,
            supports_prompt_caching=False
        )
        assert supports_prompt_caching(caps, "xai") is False
    
    def test_cache_control_for_long_message(self):
        """Test cache control config for long messages."""
        caps = ProviderCapabilities(
            max_context_length=200000,
            max_output_tokens=4096,
            supports_prompt_caching=True,
            cache_ttl_seconds=300
        )
        result = get_cache_control_config(caps, "anthropic", message_length=2000)
        assert result == {"type": "ephemeral"}
    
    def test_no_cache_control_for_short_message(self):
        """Test no cache control for short messages."""
        caps = ProviderCapabilities(
            max_context_length=200000,
            max_output_tokens=4096,
            supports_prompt_caching=True,
            cache_ttl_seconds=300
        )
        result = get_cache_control_config(caps, "anthropic", message_length=500)
        assert result is None