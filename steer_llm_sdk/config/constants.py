"""
LLM Pricing Metadata

Central location for pricing metadata and documentation.
All actual pricing values are now stored in model configurations.

See steer_llm_sdk/config/models.py for current pricing.
"""

# Pricing metadata (for auditability)
LAST_VERIFIED_PRICING_ISO = "2025-08-14"  # YYYY-MM-DD

# Official pricing documentation sources
PRICING_SOURCE_URLS = (
    # OpenAI pricing pages
    "https://platform.openai.com/pricing",
    "https://openai.com/api/pricing",
    # Anthropic pricing
    "https://www.anthropic.com/pricing", 
    "https://docs.anthropic.com/en/docs/about-claude/models#model-comparison",
    # XAI/Grok pricing
    "https://docs.x.ai/api/pricing"
)

# Pricing update instructions
PRICING_UPDATE_INSTRUCTIONS = """
To update model pricing:

1. Check the official pricing sources listed in PRICING_SOURCE_URLS
2. Update the pricing in steer_llm_sdk/config/models.py:
   - input_cost_per_1k_tokens: Cost per 1,000 input tokens
   - output_cost_per_1k_tokens: Cost per 1,000 output tokens
   - cached_input_cost_per_1k_tokens: Cost per 1,000 cached input tokens (if applicable)
3. Update LAST_VERIFIED_PRICING_ISO to today's date
4. Run tests to ensure pricing calculations still work:
   python -m pytest tests/unit/test_model_config_pricing.py
   python -m pytest tests/unit/test_selector_cost.py
"""

# Environment variable for pricing overrides
PRICING_OVERRIDES_ENV_VAR = "STEER_PRICING_OVERRIDES_JSON"

# Example pricing override format
PRICING_OVERRIDE_EXAMPLE = """
{
  "gpt-4o-mini": {
    "input_cost_per_1k_tokens": 0.00015,
    "output_cost_per_1k_tokens": 0.0006,
    "cached_input_cost_per_1k_tokens": 0.000075
  },
  "gpt-5-mini": {
    "input_cost_per_1k_tokens": 0.00025,
    "output_cost_per_1k_tokens": 0.002
  }
}
"""