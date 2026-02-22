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
        "input_cost_per_1k_tokens": 0.002,
        "output_cost_per_1k_tokens": 0.008,
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
        "input_cost_per_1k_tokens": 0.00125,
        "output_cost_per_1k_tokens": 0.01,
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

    "gpt-5-chat-latest": create_model_config("gpt-5", "gpt-5-chat-latest", {
        "name": "GPT-5 Chat Latest",
        "display_name": "GPT-5 Chat Latest",
        "description": "Latest GPT-5 optimized for chat applications",
        "max_tokens": 32768,
        "context_length": 256000,
        "input_cost_per_1k_tokens": 0.00125,
        "output_cost_per_1k_tokens": 0.01,
        "cached_input_cost_per_1k_tokens": 0.000125
    }),

    "gpt-5-codex": create_model_config("gpt-5", "gpt-5-codex", {
        "name": "GPT-5 Codex",
        "display_name": "GPT-5 Codex",
        "description": "GPT-5 optimized for code generation and understanding",
        "max_tokens": 32768,
        "context_length": 256000,
        "input_cost_per_1k_tokens": 0.00125,
        "output_cost_per_1k_tokens": 0.01,
        "cached_input_cost_per_1k_tokens": 0.000125
    }),

    "gpt-5-pro": create_model_config("gpt-5", "gpt-5-pro", {
        "name": "GPT-5 Pro",
        "display_name": "GPT-5 Pro",
        "description": "Premium GPT-5 model with maximum capabilities",
        "max_tokens": 32768,
        "context_length": 256000,
        "input_cost_per_1k_tokens": 0.015,
        "output_cost_per_1k_tokens": 0.12
    }),

    "gpt-5.1": create_model_config("gpt-5", "gpt-5.1", {
        "name": "GPT-5.1",
        "display_name": "GPT-5.1",
        "description": "Enhanced GPT-5 with improved reasoning and instruction following",
        "max_tokens": 32768,
        "context_length": 256000,
        "input_cost_per_1k_tokens": 0.00125,
        "output_cost_per_1k_tokens": 0.01,
        "cached_input_cost_per_1k_tokens": 0.000125
    }),

    "gpt-5.2": create_model_config("gpt-5", "gpt-5.2", {
        "name": "GPT-5.2",
        "display_name": "GPT-5.2",
        "description": "Latest GPT-5 series with further improvements in reasoning and capabilities",
        "max_tokens": 32768,
        "context_length": 256000,
        "input_cost_per_1k_tokens": 0.00175,
        "output_cost_per_1k_tokens": 0.014,
        "cached_input_cost_per_1k_tokens": 0.000175
    }),

    "gpt-4o-2024-05-13": create_model_config("gpt-4", "gpt-4o-2024-05-13", {
        "name": "GPT-4o (2024-05-13)",
        "display_name": "GPT-4o (2024-05-13)",
        "description": "Specific GPT-4o snapshot from May 2024",
        "max_tokens": 16384,
        "context_length": 128000,
        "input_cost_per_1k_tokens": 0.005,
        "output_cost_per_1k_tokens": 0.015
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
        "input_cost_per_1k_tokens": 0.00025,
        "output_cost_per_1k_tokens": 0.00125,
        "cached_input_cost_per_1k_tokens": 0.00003
    }),

    "claude-3-5-haiku-20241022": create_model_config("claude-3", "claude-3-5-haiku-20241022", {
        "name": "Claude 3.5 Haiku",
        "display_name": "Claude 3.5 Haiku",
        "description": "Anthropic's latest fast and efficient model with improved capabilities",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.0008,
        "output_cost_per_1k_tokens": 0.004,
        "cached_input_cost_per_1k_tokens": 0.00008
    }),

    # Claude 4 family
    "claude-haiku-4-5": create_model_config("claude-4", "claude-haiku-4-5-20251001", {
        "name": "Claude Haiku 4.5",
        "display_name": "Claude Haiku 4.5",
        "description": "Fast and cost-effective Claude 4 model, ideal for lightweight tasks",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.001,
        "output_cost_per_1k_tokens": 0.005,
        "cached_input_cost_per_1k_tokens": 0.0001
    }),

    "claude-sonnet-4": create_model_config("claude-4", "claude-sonnet-4-20250514", {
        "name": "Claude Sonnet 4",
        "display_name": "Claude Sonnet 4",
        "description": "Balanced Claude 4 model with strong reasoning and coding capabilities",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.003,
        "output_cost_per_1k_tokens": 0.015,
        "cached_input_cost_per_1k_tokens": 0.0003
    }),

    "claude-sonnet-4-5": create_model_config("claude-4", "claude-sonnet-4-5-20250929", {
        "name": "Claude Sonnet 4.5",
        "display_name": "Claude Sonnet 4.5",
        "description": "Enhanced Sonnet with improved reasoning, coding, and extended thinking",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.003,
        "output_cost_per_1k_tokens": 0.015,
        "cached_input_cost_per_1k_tokens": 0.0003
    }),

    "claude-sonnet-4-6": create_model_config("claude-4", "claude-sonnet-4-6", {
        "name": "Claude Sonnet 4.6",
        "display_name": "Claude Sonnet 4.6",
        "description": "Latest Sonnet with state-of-the-art performance at the Sonnet tier",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.003,
        "output_cost_per_1k_tokens": 0.015,
        "cached_input_cost_per_1k_tokens": 0.0003
    }),

    "claude-opus-4": create_model_config("claude-4", "claude-opus-4-20250514", {
        "name": "Claude Opus 4",
        "display_name": "Claude Opus 4",
        "description": "Anthropic's most capable model for complex analysis and extended tasks",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.015,
        "output_cost_per_1k_tokens": 0.075,
        "cached_input_cost_per_1k_tokens": 0.0015
    }),

    "claude-opus-4-1": create_model_config("claude-4", "claude-opus-4-1", {
        "name": "Claude Opus 4.1",
        "display_name": "Claude Opus 4.1",
        "description": "Enhanced Opus with improved agentic capabilities",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.015,
        "output_cost_per_1k_tokens": 0.075,
        "cached_input_cost_per_1k_tokens": 0.0015
    }),

    "claude-opus-4-5": create_model_config("claude-4", "claude-opus-4-5-20250827", {
        "name": "Claude Opus 4.5",
        "display_name": "Claude Opus 4.5",
        "description": "Premium Opus model with superior creative and analytical capabilities",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.005,
        "output_cost_per_1k_tokens": 0.025,
        "cached_input_cost_per_1k_tokens": 0.0005
    }),

    "claude-opus-4-6": create_model_config("claude-4", "claude-opus-4-6", {
        "name": "Claude Opus 4.6",
        "display_name": "Claude Opus 4.6",
        "description": "Latest and most capable Opus model with cutting-edge reasoning",
        "max_tokens": 8192,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.005,
        "output_cost_per_1k_tokens": 0.025,
        "cached_input_cost_per_1k_tokens": 0.0005
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
    
    # O-series reasoning models
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

    "o3": {
        "name": "O3",
        "display_name": "O3",
        "provider": "openai",
        "llm_model_id": "o3",
        "description": "OpenAI's flagship reasoning model with strong performance across math, coding, and science",
        "max_tokens": 100000,
        "temperature": 0.1,
        "enabled": True,
        "context_length": 200000,
        "input_cost_per_1k_tokens": 0.002,
        "output_cost_per_1k_tokens": 0.008,
        "cached_input_cost_per_1k_tokens": 0.0005
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