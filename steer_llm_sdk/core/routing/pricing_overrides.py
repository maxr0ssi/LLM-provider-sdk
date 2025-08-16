"""Pricing override functionality for model configurations."""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def load_pricing_overrides() -> Dict[str, Dict[str, float]]:
    """
    Load pricing overrides from environment variable or file.
    
    NOTE: This is an internal feature for development/debugging only.
    Requires STEER_INTERNAL_PRICING_OVERRIDES_ENABLED=true to activate.
    
    Priority order:
    1. STEER_PRICING_OVERRIDES_JSON environment variable (JSON string)
    2. STEER_PRICING_OVERRIDES_FILE environment variable (path to JSON file)
    3. ~/.steer/pricing_overrides.json (if exists)
    
    Returns:
        Dict mapping model IDs to pricing overrides
    """
    # Check if pricing overrides are enabled (internal use only)
    if os.getenv("STEER_INTERNAL_PRICING_OVERRIDES_ENABLED", "false").lower() != "true":
        return {}
    
    overrides = {}
    
    # Try JSON string from environment
    json_str = os.getenv("STEER_PRICING_OVERRIDES_JSON")
    if json_str:
        try:
            overrides = json.loads(json_str)
            logger.info(f"Loaded pricing overrides for {len(overrides)} models from environment")
            return overrides
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse STEER_PRICING_OVERRIDES_JSON: {e}")
    
    # Try file path from environment
    file_path = os.getenv("STEER_PRICING_OVERRIDES_FILE")
    if file_path:
        try:
            with open(file_path, 'r') as f:
                overrides = json.load(f)
            logger.info(f"Loaded pricing overrides for {len(overrides)} models from {file_path}")
            return overrides
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load pricing overrides from {file_path}: {e}")
    
    # Try default location
    default_path = Path.home() / ".steer" / "pricing_overrides.json"
    if default_path.exists():
        try:
            with open(default_path, 'r') as f:
                overrides = json.load(f)
            logger.info(f"Loaded pricing overrides for {len(overrides)} models from {default_path}")
            return overrides
        except json.JSONDecodeError as e:
            logger.error(f"Failed to load pricing overrides from {default_path}: {e}")
    
    return overrides


def apply_pricing_overrides(model_configs: Dict[str, Any]) -> None:
    """
    Apply pricing overrides to model configurations in-place.
    
    Args:
        model_configs: Dictionary of model configurations to update
    """
    overrides = load_pricing_overrides()
    if not overrides:
        return
    
    for model_id, pricing in overrides.items():
        if model_id not in model_configs:
            logger.warning(f"Pricing override for unknown model: {model_id}")
            continue
            
        config = model_configs[model_id]
        
        # Apply overrides
        if "input_cost_per_1k_tokens" in pricing:
            config.input_cost_per_1k_tokens = pricing["input_cost_per_1k_tokens"]
        
        if "output_cost_per_1k_tokens" in pricing:
            config.output_cost_per_1k_tokens = pricing["output_cost_per_1k_tokens"]
            
        if "cached_input_cost_per_1k_tokens" in pricing:
            config.cached_input_cost_per_1k_tokens = pricing["cached_input_cost_per_1k_tokens"]
            
        if "cost_per_1k_tokens" in pricing:
            # Legacy blended pricing
            if hasattr(config, 'cost_per_1k_tokens'):
                setattr(config, 'cost_per_1k_tokens', pricing["cost_per_1k_tokens"])
        
        logger.debug(f"Applied pricing overrides for {model_id}")


def validate_pricing_override(override: Dict[str, Any]) -> bool:
    """
    Validate a pricing override structure.
    
    Args:
        override: Single model pricing override
        
    Returns:
        True if valid, False otherwise
    """
    # Must have at least one pricing field
    pricing_fields = {
        "input_cost_per_1k_tokens",
        "output_cost_per_1k_tokens", 
        "cached_input_cost_per_1k_tokens",
        "cost_per_1k_tokens"
    }
    
    if not any(field in override for field in pricing_fields):
        return False
    
    # If exact pricing is provided, both input and output must be present
    has_input = "input_cost_per_1k_tokens" in override
    has_output = "output_cost_per_1k_tokens" in override
    
    if has_input != has_output:
        logger.warning("Pricing override must include both input and output costs")
        return False
    
    # All values must be positive numbers
    for field in pricing_fields:
        if field in override:
            value = override[field]
            if not isinstance(value, (int, float)) or value <= 0:
                logger.warning(f"Invalid pricing value for {field}: {value}")
                return False
    
    return True