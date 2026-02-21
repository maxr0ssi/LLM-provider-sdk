"""Tests for pricing override functionality."""
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from steer_llm_sdk.core.routing.pricing_overrides import (
    load_pricing_overrides,
    apply_pricing_overrides,
    validate_pricing_override
)
from steer_llm_sdk.models.generation import ModelConfig, ProviderType


class TestPricingOverrides:
    """Test pricing override functionality."""
    
    def test_disabled_by_default(self):
        """Test that pricing overrides are disabled without the internal flag."""
        overrides = {
            "gpt-4o-mini": {
                "input_cost_per_1k_tokens": 0.0002,
                "output_cost_per_1k_tokens": 0.0008
            }
        }
        
        # Without the internal flag, overrides should not be loaded
        with patch.dict(os.environ, {"STEER_PRICING_OVERRIDES_JSON": json.dumps(overrides)}):
            loaded = load_pricing_overrides()
            assert loaded == {}  # Should return empty dict
    
    def test_load_from_json_env_var(self):
        """Test loading pricing overrides from JSON environment variable."""
        overrides = {
            "gpt-4o-mini": {
                "input_cost_per_1k_tokens": 0.0002,
                "output_cost_per_1k_tokens": 0.0008
            }
        }
        
        with patch.dict(os.environ, {
            "STEER_INTERNAL_PRICING_OVERRIDES_ENABLED": "true",
            "STEER_PRICING_OVERRIDES_JSON": json.dumps(overrides)
        }):
            loaded = load_pricing_overrides()
            assert loaded == overrides
    
    def test_load_from_file_env_var(self):
        """Test loading pricing overrides from file path environment variable."""
        overrides = {
            "gpt-5-mini": {
                "input_cost_per_1k_tokens": 0.0003,
                "output_cost_per_1k_tokens": 0.0025,
                "cached_input_cost_per_1k_tokens": 0.00003
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(overrides, f)
            temp_path = f.name
        
        try:
            with patch.dict(os.environ, {
                "STEER_INTERNAL_PRICING_OVERRIDES_ENABLED": "true",
                "STEER_PRICING_OVERRIDES_FILE": temp_path
            }):
                loaded = load_pricing_overrides()
                assert loaded == overrides
        finally:
            os.unlink(temp_path)
    
    def test_load_from_default_location(self):
        """Test loading pricing overrides from default ~/.steer location."""
        overrides = {
            "o4-mini": {
                "input_cost_per_1k_tokens": 0.0012,
                "output_cost_per_1k_tokens": 0.0048
            }
        }
        
        # Create temporary home directory
        with tempfile.TemporaryDirectory() as temp_home:
            steer_dir = Path(temp_home) / ".steer"
            steer_dir.mkdir()
            override_file = steer_dir / "pricing_overrides.json"
            
            with open(override_file, 'w') as f:
                json.dump(overrides, f)
            
            # Mock Path.home() to return our temp directory
            with patch('pathlib.Path.home', return_value=Path(temp_home)):
                # Clear any pricing env vars that might interfere
                with patch.dict(os.environ, {
                    "STEER_INTERNAL_PRICING_OVERRIDES_ENABLED": "true",
                    "STEER_PRICING_OVERRIDES_JSON": "", 
                    "STEER_PRICING_OVERRIDES_FILE": ""
                }):
                    loaded = load_pricing_overrides()
                    assert loaded == overrides
    
    def test_priority_order(self):
        """Test that environment variable takes precedence over file."""
        env_overrides = {"gpt-4o-mini": {"input_cost_per_1k_tokens": 0.0002}}
        file_overrides = {"gpt-4o-mini": {"input_cost_per_1k_tokens": 0.0003}}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(file_overrides, f)
            temp_path = f.name
        
        try:
            with patch.dict(os.environ, {
                "STEER_INTERNAL_PRICING_OVERRIDES_ENABLED": "true",
                "STEER_PRICING_OVERRIDES_JSON": json.dumps(env_overrides),
                "STEER_PRICING_OVERRIDES_FILE": temp_path
            }):
                loaded = load_pricing_overrides()
                # JSON env var should take precedence
                assert loaded == env_overrides
        finally:
            os.unlink(temp_path)
    
    def test_apply_pricing_overrides(self):
        """Test applying pricing overrides to model configs."""
        # Create test model configs
        configs = {
            "test-model-1": ModelConfig(
                name="Test Model 1",
                display_name="Test Model 1",
                provider=ProviderType.OPENAI,
                llm_model_id="test-model-1",
                description="Test",
                input_cost_per_1k_tokens=0.001,
                output_cost_per_1k_tokens=0.002
            ),
            "test-model-2": ModelConfig(
                name="Test Model 2",
                display_name="Test Model 2",
                provider=ProviderType.OPENAI,
                llm_model_id="test-model-2",
                description="Test",
                input_cost_per_1k_tokens=0.002,
                output_cost_per_1k_tokens=0.004
            )
        }
        
        overrides = {
            "test-model-1": {
                "input_cost_per_1k_tokens": 0.0015,
                "output_cost_per_1k_tokens": 0.003,
                "cached_input_cost_per_1k_tokens": 0.0001
            }
        }
        
        with patch('steer_llm_sdk.core.routing.pricing_overrides.load_pricing_overrides', return_value=overrides):
            apply_pricing_overrides(configs)
            
            # Check model 1 was updated
            assert configs["test-model-1"].input_cost_per_1k_tokens == 0.0015
            assert configs["test-model-1"].output_cost_per_1k_tokens == 0.003
            assert configs["test-model-1"].cached_input_cost_per_1k_tokens == 0.0001
            
            # Check model 2 was not changed
            assert configs["test-model-2"].input_cost_per_1k_tokens == 0.002
            assert configs["test-model-2"].output_cost_per_1k_tokens == 0.004
    
    def test_validate_pricing_override(self):
        """Test pricing override validation."""
        # Valid overrides
        assert validate_pricing_override({
            "input_cost_per_1k_tokens": 0.001,
            "output_cost_per_1k_tokens": 0.002
        })
        
        assert validate_pricing_override({
            "input_cost_per_1k_tokens": 0.001,
            "output_cost_per_1k_tokens": 0.002,
            "cached_input_cost_per_1k_tokens": 0.0005
        })
        
        assert validate_pricing_override({
            "cost_per_1k_tokens": 0.0015  # Legacy blended pricing
        })
        
        # Invalid: no pricing fields
        assert not validate_pricing_override({})
        
        # Invalid: only input cost
        assert not validate_pricing_override({
            "input_cost_per_1k_tokens": 0.001
        })
        
        # Invalid: only output cost
        assert not validate_pricing_override({
            "output_cost_per_1k_tokens": 0.002
        })
        
        # Invalid: negative cost
        assert not validate_pricing_override({
            "input_cost_per_1k_tokens": -0.001,
            "output_cost_per_1k_tokens": 0.002
        })
        
        # Invalid: zero cost
        assert not validate_pricing_override({
            "input_cost_per_1k_tokens": 0,
            "output_cost_per_1k_tokens": 0.002
        })
        
        # Invalid: non-numeric cost
        assert not validate_pricing_override({
            "input_cost_per_1k_tokens": "0.001",
            "output_cost_per_1k_tokens": 0.002
        })
    
    def test_malformed_json(self):
        """Test handling of malformed JSON."""
        with patch.dict(os.environ, {
            "STEER_INTERNAL_PRICING_OVERRIDES_ENABLED": "true",
            "STEER_PRICING_OVERRIDES_JSON": "invalid json"
        }):
            loaded = load_pricing_overrides()
            assert loaded == {}  # Should return empty dict on error
    
    def test_missing_file(self):
        """Test handling of missing file."""
        with patch.dict(os.environ, {
            "STEER_INTERNAL_PRICING_OVERRIDES_ENABLED": "true",
            "STEER_PRICING_OVERRIDES_FILE": "/nonexistent/file.json"
        }):
            loaded = load_pricing_overrides()
            assert loaded == {}  # Should return empty dict on error