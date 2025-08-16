"""Normalization layer for standardizing provider interfaces.

This layer handles:
- Parameter normalization across providers
- Usage data normalization
- Streaming event normalization
- Response format standardization
"""

from .params import normalize_params
from .usage import normalize_usage

__all__ = ["normalize_params", "normalize_usage"]