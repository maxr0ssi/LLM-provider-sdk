"""Tests for ModelConfig pricing validation and functionality."""
import pytest
from steer_llm_sdk.models.generation import ModelConfig, ProviderType
from steer_llm_sdk.config.models import MODEL_CONFIGS


class TestModelConfigPricing:
    """Test ModelConfig pricing functionality."""
    
    def test_all_models_have_pricing(self):
        """Test that all enabled models have proper pricing configured."""
        for model_id, config_dict in MODEL_CONFIGS.items():
            config = ModelConfig(**config_dict)
            
            if config.enabled:
                # Check that model has either exact pricing or legacy blended pricing
                has_exact_pricing = (
                    config.input_cost_per_1k_tokens is not None and 
                    config.output_cost_per_1k_tokens is not None
                )
                has_legacy_pricing = config.cost_per_1k_tokens is not None
                
                assert has_exact_pricing or has_legacy_pricing, (
                    f"Model {model_id} must have either exact (input/output) "
                    f"or legacy (blended) pricing configured"
                )
                
                # Verify pricing values are positive
                if has_exact_pricing:
                    assert config.input_cost_per_1k_tokens > 0, (
                        f"Model {model_id} input cost must be positive"
                    )
                    assert config.output_cost_per_1k_tokens > 0, (
                        f"Model {model_id} output cost must be positive"
                    )
                    
                if has_legacy_pricing:
                    assert config.cost_per_1k_tokens > 0, (
                        f"Model {model_id} legacy cost must be positive"
                    )
    
    def test_cached_pricing_less_than_regular(self):
        """Test that cached input pricing is less than regular input pricing."""
        for model_id, config_dict in MODEL_CONFIGS.items():
            config = ModelConfig(**config_dict)
            
            if config.cached_input_cost_per_1k_tokens is not None:
                assert config.input_cost_per_1k_tokens is not None, (
                    f"Model {model_id} has cached pricing but no regular input pricing"
                )
                assert config.cached_input_cost_per_1k_tokens < config.input_cost_per_1k_tokens, (
                    f"Model {model_id} cached pricing must be less than regular input pricing"
                )
    
    def test_pricing_validation_both_required(self):
        """Test that both input and output costs must be set together."""
        # Valid config with both prices
        valid_config = {
            "name": "Test Model",
            "display_name": "Test Model",
            "provider": ProviderType.OPENAI,
            "llm_model_id": "test-model",
            "description": "Test model",
            "input_cost_per_1k_tokens": 0.001,
            "output_cost_per_1k_tokens": 0.002
        }
        config = ModelConfig(**valid_config)
        assert config.input_cost_per_1k_tokens == 0.001
        assert config.output_cost_per_1k_tokens == 0.002
        
        # Invalid: only input cost
        invalid_config1 = {
            "name": "Test Model",
            "display_name": "Test Model", 
            "provider": ProviderType.OPENAI,
            "llm_model_id": "test-model",
            "description": "Test model",
            "input_cost_per_1k_tokens": 0.001
        }
        with pytest.raises(ValueError, match="output_cost_per_1k_tokens"):
            ModelConfig(**invalid_config1)
        
        # Invalid: only output cost
        invalid_config2 = {
            "name": "Test Model",
            "display_name": "Test Model",
            "provider": ProviderType.OPENAI,
            "llm_model_id": "test-model",
            "description": "Test model",
            "output_cost_per_1k_tokens": 0.002
        }
        with pytest.raises(ValueError, match="input_cost_per_1k_tokens"):
            ModelConfig(**invalid_config2)
    
    def test_legacy_pricing_allowed_alone(self):
        """Test that legacy blended pricing can be set without input/output costs."""
        config = ModelConfig(
            name="Test Model",
            display_name="Test Model",
            provider=ProviderType.OPENAI,
            llm_model_id="test-model",
            description="Test model",
            cost_per_1k_tokens=0.0015  # Legacy blended rate
        )
        assert config.cost_per_1k_tokens == 0.0015
        assert config.input_cost_per_1k_tokens is None
        assert config.output_cost_per_1k_tokens is None
    
    def test_openai_models_pricing(self):
        """Test specific OpenAI model pricing matches expectations."""
        # GPT-4o-mini
        config = ModelConfig(**MODEL_CONFIGS["gpt-4o-mini"])
        assert config.input_cost_per_1k_tokens == 0.00015  # $0.15 per 1M
        assert config.output_cost_per_1k_tokens == 0.0006   # $0.60 per 1M
        assert config.cached_input_cost_per_1k_tokens == 0.000075  # $0.075 per 1M
        
        # GPT-5-mini
        config = ModelConfig(**MODEL_CONFIGS["gpt-5-mini"])
        assert config.input_cost_per_1k_tokens == 0.00025  # $0.25 per 1M
        assert config.output_cost_per_1k_tokens == 0.002    # $2.00 per 1M
        assert config.cached_input_cost_per_1k_tokens == 0.000025  # $0.025 per 1M
        
        # O4-mini
        config = ModelConfig(**MODEL_CONFIGS["o4-mini"])
        assert config.input_cost_per_1k_tokens == 0.0011   # $1.10 per 1M
        assert config.output_cost_per_1k_tokens == 0.0044  # $4.40 per 1M
        assert config.cached_input_cost_per_1k_tokens == 0.000275  # $0.275 per 1M