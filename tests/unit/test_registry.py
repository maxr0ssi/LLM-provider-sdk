"""Unit tests for LLM registry functionality."""

import pytest
from unittest.mock import patch, Mock
import time

from steer_llm_sdk.core.routing import (
    get_config,
    get_available_models,
    is_model_available,
    check_lightweight_availability,
    normalize_params,
    calculate_cost,
    get_default_hyperparameters,
    MODEL_CONFIGS
)
from steer_llm_sdk.models.generation import ModelConfig, GenerationParams, ProviderType


class TestRegistry:
    """Test registry functions."""
    
    def test_get_config_existing_model(self):
        """Test getting config for existing model."""
        # Test with actual model ID from configs
        config = get_config("gpt-4o-mini")
        assert isinstance(config, ModelConfig)
        assert config.provider == ProviderType.OPENAI
    
    def test_get_config_nonexistent_model(self):
        """Test getting config for non-existent model defaults to DEFAULT_MODEL."""
        config = get_config("NonExistentModel")
        assert isinstance(config, ModelConfig)
        # Should return default model config
    
    def test_get_available_models(self):
        """Test getting only enabled models."""
        models = get_available_models()
        assert isinstance(models, dict)
        # All returned models should be enabled
        for model_id, config in models.items():
            assert config.enabled is True
    
    def test_is_model_available(self):
        """Test checking model availability."""
        # Test with a known enabled model
        assert is_model_available("gpt-4o-mini") is True
        
        # Test with non-existent model
        assert is_model_available("NonExistentModel") is False
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_check_lightweight_availability_openai(self):
        """Test lightweight availability check for OpenAI."""
        # Mock a config with OpenAI provider
        with patch('steer_llm_sdk.core.routing.selector.get_config') as mock_get_config:
            mock_get_config.return_value = ModelConfig(
                name="test",
                display_name="Test",
                provider=ProviderType.OPENAI,
                llm_model_id="test",
                description="Test",
                enabled=True
            )
            
            assert check_lightweight_availability("test-model") is True
    
    def test_check_lightweight_availability_no_api_key(self):
        """Test lightweight availability check without API key."""
        # Clear cache first
        from steer_llm_sdk.core.routing.selector import _model_status_cache
        _model_status_cache.clear()
        
        with patch.dict('os.environ', {}, clear=True):
            with patch('steer_llm_sdk.core.routing.selector.get_config') as mock_get_config:
                mock_get_config.return_value = ModelConfig(
                    name="test",
                    display_name="Test", 
                    provider=ProviderType.OPENAI,
                    llm_model_id="test",
                    description="Test",
                    enabled=True
                )
                
                assert check_lightweight_availability("test-model") is False
    
    def test_check_lightweight_availability_caching(self):
        """Test that availability results are cached."""
        with patch('steer_llm_sdk.core.routing.selector.get_config') as mock_get_config:
            mock_get_config.return_value = ModelConfig(
                name="test",
                display_name="Test",
                provider=ProviderType.OPENAI,
                llm_model_id="test",
                description="Test",
                enabled=True
            )
            
            # Clear cache
            from steer_llm_sdk.core.routing.selector import _model_status_cache
            _model_status_cache.clear()
            
            # First call
            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key', 'STEER_SDK_BYPASS_AVAILABILITY_CHECK': 'false'}):
                result1 = check_lightweight_availability("test-model")
            
            # Second call should use cache
            with patch.dict('os.environ', {'STEER_SDK_BYPASS_AVAILABILITY_CHECK': 'false'}, clear=True):
                result2 = check_lightweight_availability("test-model")
            
            # Should return same result due to cache
            assert result1 == result2
    
    def test_normalize_params(self):
        """Test parameter normalization."""
        raw_params = {
            "max_tokens": 200,
            "temperature": 0.8,
            "topP": 0.9,  # Test camelCase conversion
            "frequencyPenalty": 0.1,
            "presencePenalty": 0.2
        }
        
        config = ModelConfig(
            name="test",
            display_name="Test",
            provider=ProviderType.OPENAI,
            llm_model_id="test-model",
            description="Test",
            max_tokens=1000,
            temperature=0.7
        )
        
        params = normalize_params(raw_params, config)
        
        assert isinstance(params, GenerationParams)
        assert params.model == "test-model"
        assert params.max_tokens == 200
        assert params.temperature == 0.8
        assert params.top_p == 0.9
        assert params.frequency_penalty == 0.1
        assert params.presence_penalty == 0.2
    
    def test_normalize_params_max_tokens_limit(self):
        """Test that max_tokens is limited by model config."""
        raw_params = {"max_tokens": 5000}
        
        config = ModelConfig(
            name="test",
            display_name="Test",
            provider=ProviderType.OPENAI,
            llm_model_id="test-model",
            description="Test",
            max_tokens=1000  # Model limit
        )
        
        params = normalize_params(raw_params, config)
        assert params.max_tokens == 1000  # Should be capped at model limit
    
    def test_calculate_cost_with_pricing(self):
        """Test cost calculation with pricing info."""
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500
        }
        
        config = ModelConfig(
            name="test",
            display_name="Test",
            provider=ProviderType.OPENAI,
            llm_model_id="test",
            description="Test",
            cost_per_1k_tokens=0.001  # $0.001 per 1k tokens
        )
        
        cost = calculate_cost(usage, config)
        assert cost == 0.0015  # 1.5k tokens * $0.001/1k
    
    def test_calculate_cost_no_pricing(self):
        """Test cost calculation without pricing info."""
        usage = {"prompt_tokens": 1000, "completion_tokens": 500}
        
        config = ModelConfig(
            name="test",
            display_name="Test",
            provider=ProviderType.OPENAI,
            llm_model_id="test",
            description="Test",
            cost_per_1k_tokens=None
        )
        
        cost = calculate_cost(usage, config)
        assert cost is None
    
    def test_get_default_hyperparameters(self):
        """Test getting default hyperparameters."""
        # Test without provider
        params = get_default_hyperparameters()
        assert isinstance(params, dict)
        
        # Test with specific provider (if configured)
        params = get_default_hyperparameters("openai")
        assert isinstance(params, dict)