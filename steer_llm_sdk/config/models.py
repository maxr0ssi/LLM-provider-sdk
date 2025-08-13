# Model configurations - raw data only
MODEL_CONFIGS = {
    "gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "display_name": "GPT-4o Mini",
        "provider": "openai",
        "llm_model_id": "gpt-4o-mini",
        "description": "Smaller version of GPT-4o, faster and more cost-effective",
        "max_tokens": 8192,
        "temperature": 0.7,
        "enabled": True,
        "input_cost_per_1k_tokens": 0.00015,  # $0.15 per 1M = $0.00015 per 1K
        "output_cost_per_1k_tokens": 0.0006   # $0.60 per 1M = $0.0006 per 1K
    },
    "gpt-4.1-nano": {
        "name": "GPT-4.1 Nano",
        "display_name": "GPT-4.1 Nano",
        "provider": "openai",
        "llm_model_id": "gpt-4.1-nano",
        "description": "Ultra-efficient nano model, perfect for simple evaluations and cost optimization",
        "max_tokens": 2048,
        "temperature": 0.7,
        "enabled": True,
        "input_cost_per_1k_tokens": 0.0001,   # $0.10 per 1M = $0.0001 per 1K
        "output_cost_per_1k_tokens": 0.0004   # $0.40 per 1M = $0.0004 per 1K
    },
    "grok-3-mini": {
        "name": "Grok 3 Mini",
        "display_name": "Grok 3 Mini",
        "provider": "xai",
        "llm_model_id": "grok-3-mini",
        "description": "Cost-effective mini version of Grok 3, optimized for lower latency and expense",
        "max_tokens": 8192,
        "temperature": 0.7,
        "enabled": True,
        "input_cost_per_1k_tokens": 0.0003,   # $0.30 per 1M = $0.0003 per 1K
        "output_cost_per_1k_tokens": 0.0005   # $0.50 per 1M = $0.0005 per 1K
    },

    "gpt-5-mini": {
        "name": "GPT-5 Mini",
        "display_name": "GPT-5 Mini",
        "provider": "openai",
        "llm_model_id": "gpt-5-mini",
        "description": "Next-generation mini model with full Responses API support and larger context window",
        "max_tokens": 32768,
        "temperature": 0.7,
        "enabled": True,
        "context_length": 256000,  # 256K context window
        "input_cost_per_1k_tokens": 0.00025,   # $0.250 per 1M = $0.00025 per 1K
        "output_cost_per_1k_tokens": 0.002,    # $2.000 per 1M = $0.002 per 1K
        "cached_input_cost_per_1k_tokens": 0.000025  # $0.025 per 1M = $0.000025 per 1K
    },

    "gpt-3.5-turbo": {
        "name": "GPT-3.5 Turbo",
        "display_name": "GPT-3.5 Turbo",
        "provider": "openai",
        "llm_model_id": "gpt-3.5-turbo",
        "description": "Fast and efficient model, good for general tasks",
        "max_tokens": 4096,
        "temperature": 0.7,
        "enabled": True,
        "input_cost_per_1k_tokens": 0.0005,   # $0.50 per 1M = $0.0005 per 1K
        "output_cost_per_1k_tokens": 0.0015   # $1.50 per 1M = $0.0015 per 1K
    },
    "claude-3-haiku": {
        "name": "Claude 3 Haiku",
        "display_name": "Claude 3",
        "provider": "anthropic",
        "llm_model_id": "claude-3-haiku-20240307",
        "description": "Anthropic's fastest and most cost-effective model.\nGreat balance of speed, intelligence, and affordability",
        "max_tokens": 4096,
        "temperature": 0.7,
        "enabled": True,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.0003,   # $0.30 per 1M = $0.0003 per 1K (Anthropic pricing estimated)
        "output_cost_per_1k_tokens": 0.0015,  # $1.50 per 1M = $0.0015 per 1K
        "cached_input_cost_per_1k_tokens": 0.00007  # ~$0.07 per 1M = $0.00007 per 1K
    },
    "o4-mini": {
        "name": "O4 Mini",
        "display_name": "O4 Mini",
        "provider": "openai",
        "llm_model_id": "o4-mini-2025-04-16",
        "description": "OpenAI's smaller reasoning model optimized for fast, cost-efficient reasoning.\nExcellent performance in math, coding, and visual tasks",
        "max_tokens": 100000,
        "temperature": 0.1,
        "enabled": True,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.0011,   # $1.10 per 1M = $0.0011 per 1K
        "output_cost_per_1k_tokens": 0.0044,  # $4.40 per 1M = $0.0044 per 1K
        "cached_input_cost_per_1k_tokens": 0.000275  # $0.275 per 1M = $0.000275 per 1K
    },
    "gpt-4.1-mini": {
        "name": "GPT-4.1 Mini",
        "display_name": "GPT-4.1 Mini",
        "provider": "openai",
        "llm_model_id": "gpt-4.1-mini-2025-04-14",
        "description": "OpenAI's latest mini model with enhanced capabilities and cost efficiency",
        "max_tokens": 16384,
        "temperature": 0.1,
        "enabled": True,
        "input_cost_per_1k_tokens": 0.0004,   # $0.40 per 1M = $0.0004 per 1K
        "output_cost_per_1k_tokens": 0.0016,  # $1.60 per 1M = $0.0016 per 1K
        "cached_input_cost_per_1k_tokens": 0.0001  # $0.10 per 1M = $0.0001 per 1K
    }
}

# Default model
DEFAULT_MODEL = "gpt-4o-mini"

# Provider-specific hyperparameter configurations
PROVIDER_HYPERPARAMETERS = {
    "openai": {
        "max_tokens": 500,
        "temperature": 0.7,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    },
    "anthropic": {
        "max_tokens": 500,
        "temperature": 0.7,
        "top_p": 1.0,
        "top_k": 250,  # Anthropic-specific parameter instead of frequency/presence penalty
    },
        "xai": {
        "max_tokens": 500,
        "temperature": 0.7,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }
}

# Default fallback hyperparameters (primarily for OpenAI compatibility)
DEFAULT_MODEL_HYPERPARAMETERS = PROVIDER_HYPERPARAMETERS["openai"]