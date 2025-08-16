# Model configurations using family inheritance
from .model_families import create_model_config

# Model configurations with family inheritance
MODEL_CONFIGS = {
    # GPT-4 Family
    "gpt-4o-mini": create_model_config("gpt-4", "gpt-4o-mini", {
        "name": "GPT-4o Mini",
        "display_name": "GPT-4o Mini",
        "description": "Smaller version of GPT-4o, faster and more cost-effective",
        "max_tokens": 8192,
        "input_cost_per_1k_tokens": 0.00015,
        "output_cost_per_1k_tokens": 0.0006,
        "cached_input_cost_per_1k_tokens": 0.000075
    }),
    
    "gpt-4o": create_model_config("gpt-4", "gpt-4o", {
        "name": "GPT-4o",
        "display_name": "GPT-4o",
        "description": "Optimized GPT-4 with enhanced performance and efficiency",
        "max_tokens": 16384,
        "context_length": 128000,
        "input_cost_per_1k_tokens": 0.0025,
        "output_cost_per_1k_tokens": 0.01,
        "cached_input_cost_per_1k_tokens": 0.00125
    }),
    
    # GPT-4.1 Family
    "gpt-4.1-nano": create_model_config("gpt-4.1", "gpt-4.1-nano", {
        "name": "GPT-4.1 Nano",
        "display_name": "GPT-4.1 Nano",
        "description": "Ultra-efficient nano model, perfect for simple evaluations and cost optimization",
        "max_tokens": 2048,
        "input_cost_per_1k_tokens": 0.0001,
        "output_cost_per_1k_tokens": 0.0004,
        "cached_input_cost_per_1k_tokens": 0.000025
    }),
    
    "gpt-4.1-mini": create_model_config("gpt-4.1", "gpt-4.1-mini-2025-04-14", {
        "name": "GPT-4.1 Mini",
        "display_name": "GPT-4.1 Mini",
        "description": "OpenAI's latest mini model with enhanced capabilities and cost efficiency",
        "max_tokens": 16384,
        "temperature": 0.1,
        "input_cost_per_1k_tokens": 0.0004,
        "output_cost_per_1k_tokens": 0.0016,
        "cached_input_cost_per_1k_tokens": 0.0001
    }),
    
    "gpt-4.1": create_model_config("gpt-4.1", "gpt-4.1", {
        "name": "GPT-4.1",
        "display_name": "GPT-4.1",
        "description": "Enhanced GPT-4 with improved reasoning and larger context window",
        "max_tokens": 16384,
        "context_length": 128000,
        "cached_input_cost_per_1k_tokens": 0.0005
    }),
    
    # GPT-5 Family
    "gpt-5-mini": create_model_config("gpt-5", "gpt-5-mini", {
        "name": "GPT-5 Mini",
        "display_name": "GPT-5 Mini",
        "description": "Next-generation mini model with full Responses API support and larger context window",
        "max_tokens": 32768,
        "context_length": 256000,
        "input_cost_per_1k_tokens": 0.00025,
        "output_cost_per_1k_tokens": 0.002,
        "cached_input_cost_per_1k_tokens": 0.000025
    }),
    
    "gpt-5": create_model_config("gpt-5", "gpt-5", {
        "name": "GPT-5",
        "display_name": "GPT-5",
        "description": "OpenAI's most advanced flagship model with superior reasoning capabilities",
        "max_tokens": 32768,
        "context_length": 256000,
        "cached_input_cost_per_1k_tokens": 0.000125
    }),
    
    "gpt-5-nano": create_model_config("gpt-5", "gpt-5-nano", {
        "name": "GPT-5 Nano",
        "display_name": "GPT-5 Nano",
        "description": "Ultra-efficient nano version of GPT-5 for maximum cost optimization",
        "max_tokens": 8192,
        "context_length": 128000,
        "input_cost_per_1k_tokens": 0.00005,
        "output_cost_per_1k_tokens": 0.0004,
        "cached_input_cost_per_1k_tokens": 0.000005
    }),
    
    # Legacy models (not using family inheritance)
    "gpt-3.5-turbo": {
        "name": "GPT-3.5 Turbo",
        "display_name": "GPT-3.5 Turbo",
        "provider": "openai",
        "llm_model_id": "gpt-3.5-turbo",
        "description": "Fast and efficient model, good for general tasks",
        "max_tokens": 4096,
        "temperature": 0.7,
        "enabled": True,
        "input_cost_per_1k_tokens": 0.0005,
        "output_cost_per_1k_tokens": 0.0015,
    },
    
    # Claude models
    "claude-3-haiku": create_model_config("claude-3", "claude-3-haiku-20240307", {
        "name": "Claude 3 Haiku",
        "display_name": "Claude 3",
        "description": "Anthropic's fastest and most cost-effective model.\nGreat balance of speed, intelligence, and affordability",
        "max_tokens": 4096,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.0003,
        "output_cost_per_1k_tokens": 0.0015,
        "cached_input_cost_per_1k_tokens": 0.00007
    }),
    
    "claude-3-5-haiku-20241022": create_model_config("claude-3", "claude-3-5-haiku-20241022", {
        "name": "Claude 3.5 Haiku",
        "display_name": "Claude 3.5 Haiku",
        "description": "Anthropic's latest fast and efficient model with improved capabilities",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.001,
        "output_cost_per_1k_tokens": 0.005,
        "cached_input_cost_per_1k_tokens": 0.0001
    }),
    
    # xAI models
    "grok-3-mini": create_model_config("grok", "grok-3-mini", {
        "name": "Grok 3 Mini",
        "display_name": "Grok 3 Mini",
        "description": "Cost-effective mini version of Grok 3, optimized for lower latency and expense",
        "max_tokens": 8192,
        "input_cost_per_1k_tokens": 0.0003,
        "output_cost_per_1k_tokens": 0.0005
    }),
    
    # O4 model (OpenAI reasoning)
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
        "input_cost_per_1k_tokens": 0.0011,
        "output_cost_per_1k_tokens": 0.0044,
        "cached_input_cost_per_1k_tokens": 0.000275
    },
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