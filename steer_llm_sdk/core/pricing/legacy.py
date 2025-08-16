"""Legacy pricing support for backward compatibility.

This module centralizes legacy blended pricing fallbacks that are used
in tests and older configurations. This will be removed in a future version.
"""

from typing import Dict, Any, Optional
from ...models.generation import ModelConfig


def get_legacy_blended_pricing(config: ModelConfig, usage: Dict[str, Any]) -> Optional[float]:
    """Calculate cost using legacy blended pricing if available.
    
    This is a fallback for tests and backward compatibility only.
    New code should use the pricing_input/pricing_output fields.
    
    Args:
        config: Model configuration
        usage: Usage dictionary with token counts
        
    Returns:
        Cost in USD if legacy pricing is available, None otherwise
    """
    if not hasattr(config, 'pricing'):
        return None
        
    pricing = config.pricing
    if not pricing:
        return None
        
    # Legacy blended single-rate pricing
    total_tokens = usage.get('total_tokens', 0)
    if total_tokens and isinstance(pricing, (int, float)):
        return (total_tokens / 1000.0) * float(pricing)
        
    return None


def has_legacy_pricing(config: ModelConfig) -> bool:
    """Check if a model config has legacy pricing defined.
    
    Args:
        config: Model configuration
        
    Returns:
        True if legacy pricing is available
    """
    return (
        hasattr(config, 'pricing') and 
        config.pricing is not None and
        isinstance(config.pricing, (int, float))
    )