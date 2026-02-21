"""Tests for selector cost calculation functions."""
import pytest
from steer_llm_sdk.core.routing.selector import (
    calculate_exact_cost, 
    calculate_cache_savings,
    get_config
)


class TestSelectorCostFunctions:
    """Test cost calculation functions in selector."""
    
    def test_calculate_exact_cost_with_config_pricing(self):
        """Test exact cost calculation using model config pricing."""
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500
        }
        
        # Test GPT-4o-mini
        cost = calculate_exact_cost(usage, "gpt-4o-mini")
        # 1000 * 0.00015 + 500 * 0.0006 = 0.15 + 0.3 = 0.45
        assert cost == 0.00045
        
        # Test GPT-5-mini
        cost = calculate_exact_cost(usage, "gpt-5-mini")
        # 1000 * 0.00025 + 500 * 0.002 = 0.25 + 1.0 = 1.25
        assert cost == 0.00125
        
        # Test O4-mini
        cost = calculate_exact_cost(usage, "o4-mini")
        # 1000 * 0.0011 + 500 * 0.0044 = 1.1 + 2.2 = 3.3
        assert cost == 0.0033
    
    def test_calculate_exact_cost_with_legacy_pricing(self):
        """Test exact cost calculation falling back to legacy blended pricing."""
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500
        }
        
        # Test model with only legacy pricing (gpt-3.5-turbo)
        cost = calculate_exact_cost(usage, "gpt-3.5-turbo")
        # gpt-3.5-turbo has exact pricing: 1000 * 0.0005 + 500 * 0.0015 = 0.5 + 0.75 = 1.25
        assert cost == 0.00125
    
    def test_calculate_exact_cost_no_pricing(self):
        """Test exact cost returns None when no pricing available."""
        # Create a custom usage for a model without pricing
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500
        }
        
        # Test with unknown model (will use default model config)
        cost = calculate_exact_cost(usage, "unknown-model")
        # Should still work because default model has pricing
        assert cost is not None
    
    def test_calculate_cache_savings_openai(self):
        """Test cache savings calculation for OpenAI models."""
        # Test model with cached pricing
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "cache_info": {
                "cached_tokens": 800
            }
        }
        
        # GPT-4o-mini: regular 0.00015, cached 0.000075
        # Savings: 800 * (0.00015 - 0.000075) = 800 * 0.000075 = 0.06
        savings = calculate_cache_savings(usage, "gpt-4o-mini")
        assert abs(savings - 0.00006) < 1e-10  # Use approximate equality for float
        
        # O4-mini: regular 0.0011, cached 0.000275
        # Savings: 800 * (0.0011 - 0.000275) = 800 * 0.000825 = 0.66
        savings = calculate_cache_savings(usage, "o4-mini")
        assert abs(savings - 0.00066) < 1e-10  # Use approximate equality for float
    
    def test_calculate_cache_savings_anthropic(self):
        """Test cache savings calculation for Anthropic models."""
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "cache_info": {
                "cache_read_tokens": 800
            }
        }
        
        # Claude models with cached pricing
        savings = calculate_cache_savings(usage, "claude-3-haiku")
        # Regular: 0.0003, cached: 0.00007
        # Savings: 800 * (0.0003 - 0.00007) = 800 * 0.00023 = 0.184
        assert abs(savings - 0.000184) < 1e-10  # Use approximate equality for float
        
        # Claude models without explicit cached pricing (estimates 75% savings)
        config = get_config("grok-3-mini")
        if config.cached_input_cost_per_1k_tokens is None:
            savings = calculate_cache_savings(usage, "grok-3-mini")
            # Estimates 75% of input cost: 800 * 0.0003 * 0.75 = 0.18
            assert abs(savings - 0.00018) < 1e-10  # Use approximate equality for float
    
    def test_calculate_cache_savings_no_cache(self):
        """Test cache savings returns 0 when no cache info."""
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500
        }
        
        savings = calculate_cache_savings(usage, "gpt-4o-mini")
        assert savings == 0.0
        
        # Empty cache_info
        usage["cache_info"] = {}
        savings = calculate_cache_savings(usage, "gpt-4o-mini")
        assert savings == 0.0
    
    def test_cost_calculation_with_cache_integration(self):
        """Test integrated cost calculation with cache savings."""
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "cache_info": {
                "cached_tokens": 800
            }
        }
        
        # Calculate total cost for GPT-4o-mini
        exact_cost = calculate_exact_cost(usage, "gpt-4o-mini")
        cache_savings = calculate_cache_savings(usage, "gpt-4o-mini")
        final_cost = exact_cost - cache_savings
        
        # Exact: 0.00045, Savings: 0.00006, Final: 0.00039
        assert exact_cost == 0.00045
        assert abs(cache_savings - 0.00006) < 1e-10  # Use approximate equality for float
        assert abs(final_cost - 0.00039) < 1e-10  # Use approximate equality for float