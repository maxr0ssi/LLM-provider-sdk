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

        # O3
        config = ModelConfig(**MODEL_CONFIGS["o3"])
        assert config.input_cost_per_1k_tokens == 0.002    # $2.00 per 1M
        assert config.output_cost_per_1k_tokens == 0.008   # $8.00 per 1M
        assert config.cached_input_cost_per_1k_tokens == 0.0005  # $0.50 per 1M

        # GPT-5.1
        config = ModelConfig(**MODEL_CONFIGS["gpt-5.1"])
        assert config.input_cost_per_1k_tokens == 0.00125  # $1.25 per 1M
        assert config.output_cost_per_1k_tokens == 0.01    # $10.00 per 1M
        assert config.cached_input_cost_per_1k_tokens == 0.000125  # $0.125 per 1M

        # GPT-5.2
        config = ModelConfig(**MODEL_CONFIGS["gpt-5.2"])
        assert config.input_cost_per_1k_tokens == 0.00175  # $1.75 per 1M
        assert config.output_cost_per_1k_tokens == 0.014   # $14.00 per 1M
        assert config.cached_input_cost_per_1k_tokens == 0.000175  # $0.175 per 1M

    def test_claude_models_pricing(self):
        """Test specific Anthropic model pricing matches expectations."""
        # Claude 3 Haiku
        config = ModelConfig(**MODEL_CONFIGS["claude-3-haiku"])
        assert config.input_cost_per_1k_tokens == 0.00025   # $0.25 per 1M
        assert config.output_cost_per_1k_tokens == 0.00125  # $1.25 per 1M
        assert config.cached_input_cost_per_1k_tokens == 0.00003  # $0.03 per 1M

        # Claude 3.5 Haiku
        config = ModelConfig(**MODEL_CONFIGS["claude-3-5-haiku-20241022"])
        assert config.input_cost_per_1k_tokens == 0.0008   # $0.80 per 1M
        assert config.output_cost_per_1k_tokens == 0.004    # $4.00 per 1M
        assert config.cached_input_cost_per_1k_tokens == 0.00008  # $0.08 per 1M

        # Claude Haiku 4.5
        config = ModelConfig(**MODEL_CONFIGS["claude-haiku-4-5"])
        assert config.input_cost_per_1k_tokens == 0.001    # $1.00 per 1M
        assert config.output_cost_per_1k_tokens == 0.005    # $5.00 per 1M
        assert config.cached_input_cost_per_1k_tokens == 0.0001  # $0.10 per 1M

        # Claude Sonnet 4 / 4.5 / 4.6 — all $3/$15/$0.30 per MTok
        for model_id in ("claude-sonnet-4", "claude-sonnet-4-5", "claude-sonnet-4-6"):
            config = ModelConfig(**MODEL_CONFIGS[model_id])
            assert config.input_cost_per_1k_tokens == 0.003, f"{model_id} input"
            assert config.output_cost_per_1k_tokens == 0.015, f"{model_id} output"
            assert config.cached_input_cost_per_1k_tokens == 0.0003, f"{model_id} cached"

        # Claude Opus 4 / 4.1 — $15/$75/$1.50 per MTok
        for model_id in ("claude-opus-4", "claude-opus-4-1"):
            config = ModelConfig(**MODEL_CONFIGS[model_id])
            assert config.input_cost_per_1k_tokens == 0.015, f"{model_id} input"
            assert config.output_cost_per_1k_tokens == 0.075, f"{model_id} output"
            assert config.cached_input_cost_per_1k_tokens == 0.0015, f"{model_id} cached"

        # Claude Opus 4.5 / 4.6 — $5/$25/$0.50 per MTok
        for model_id in ("claude-opus-4-5", "claude-opus-4-6"):
            config = ModelConfig(**MODEL_CONFIGS[model_id])
            assert config.input_cost_per_1k_tokens == 0.005, f"{model_id} input"
            assert config.output_cost_per_1k_tokens == 0.025, f"{model_id} output"
            assert config.cached_input_cost_per_1k_tokens == 0.0005, f"{model_id} cached"