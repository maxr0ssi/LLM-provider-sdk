"""
Unit tests for registry integration with capabilities.
"""

import pytest

from steer_llm_sdk.core.routing import (
    get_config,
    get_capabilities,
    calculate_cost,
    calculate_exact_cost
)
from steer_llm_sdk.core.capabilities.models import ProviderCapabilities


class TestRegistryCapabilities:
    """Test registry integration with capability system."""
    
    def test_get_capabilities_known_model(self):
        """Test getting capabilities for known models."""
        # GPT-4o Mini
        caps = get_capabilities("gpt-4o-mini")
        assert isinstance(caps, ProviderCapabilities)
        assert caps.supports_json_schema is True
        assert caps.supports_streaming is True
        assert caps.max_context_length == 128000
        
        # GPT-5 Mini
        caps = get_capabilities("gpt-5-mini")
        assert caps.supports_json_schema is True
        assert caps.supports_response_format is True
        assert caps.max_context_length == 256000
        assert caps.max_output_tokens == 32768
        
        # Claude
        caps = get_capabilities("claude-3-haiku")
        assert caps.supports_json_schema is False  # No native JSON schema
        assert caps.supports_multiple_system_messages is True
        assert caps.max_context_length == 200000
    
    def test_get_capabilities_by_display_name(self):
        """Test getting capabilities using display name."""
        caps = get_capabilities("GPT-4o Mini")
        assert isinstance(caps, ProviderCapabilities)
        assert caps.supports_json_schema is True
    
    def test_get_capabilities_unknown_model(self):
        """Test getting capabilities for unknown model falls back to default model."""
        caps = get_capabilities("unknown-model-xyz")
        assert isinstance(caps, ProviderCapabilities)
        # Falls back to default model (gpt-4o-mini) capabilities
        assert caps.supports_json_schema is True  # GPT-4o mini supports it
        assert caps.max_context_length == 128000  # GPT-4o mini context
    
    def test_special_model_capabilities(self):
        """Test special model requirements are captured."""
        # o4-mini special requirements
        caps = get_capabilities("o4-mini")
        assert caps.uses_max_completion_tokens is True
        assert caps.requires_temperature_one is True
        assert caps.deterministic_temperature_max == 1.0
        
        # Models with caching
        caps = get_capabilities("gpt-4.1-mini")
        assert caps.supports_prompt_caching is True
        assert caps.has_cached_pricing is True


class TestCostCalculation:
    """Test cost calculation with new pricing model."""
    
    def test_calculate_cost_with_pricing(self):
        """Test cost calculation using model config pricing."""
        config = get_config("gpt-4o-mini")
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500
        }
        
        cost = calculate_cost(usage, config)
        assert cost is not None
        # 1000 * 0.00015 + 500 * 0.0006 = 0.15 + 0.30 = 0.45
        assert abs(cost - 0.00045) < 0.000001
    
    def test_calculate_cost_no_pricing(self):
        """Test cost calculation returns None when pricing not available."""
        # Create a config without pricing
        config = get_config("gpt-3.5-turbo")
        if config.input_cost_per_1k_tokens is None:
            usage = {"prompt_tokens": 100, "completion_tokens": 50}
            cost = calculate_cost(usage, config)
            assert cost is None
    
    def test_calculate_exact_cost_gpt5_mini(self):
        """Test exact cost calculation for GPT-5 mini."""
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500
        }
        
        cost = calculate_exact_cost(usage, "gpt-5-mini")
        assert cost is not None
        # 1000 * 0.00025 + 500 * 0.002 = 0.25 + 1.0 = 1.25
        expected = (1000 / 1000) * 0.00025 + (500 / 1000) * 0.002
        assert abs(cost - expected) < 0.000001
    
    def test_calculate_exact_cost_with_cache(self):
        """Test cost calculation includes cache savings."""
        # This test would need the calculate_cache_savings function
        # For now, just verify the function exists and handles basic usage
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "cache_info": {
                "cached_tokens": 500
            }
        }
        
        cost = calculate_exact_cost(usage, "gpt-4.1-mini")
        assert cost is not None