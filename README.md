# Steer LLM SDK

A unified Python SDK for integrating multiple LLM providers with normalized APIs, streaming support, and advanced features.

## Features

- **Multi-Provider Support**: Seamlessly work with OpenAI, Anthropic, xAI, and local HuggingFace models
- **Normalized API**: Consistent interface across all providers
- **Streaming Support**: Real-time text generation with async streaming
- **Conversation Management**: Built-in support for multi-turn conversations
- **Parameter Validation**: Automatic validation and normalization of generation parameters
- **Cost Tracking**: Calculate and track API usage costs
- **Model Registry**: Centralized configuration for all supported models
- **Lightweight Availability Checks**: Verify model availability without loading

## Installation

```bash
pip install steer-llm-sdk
```

For local model support:
```bash
pip install steer-llm-sdk[local]
```

## Quick Start

```python
from steer_llm_sdk import LLMRouter, GenerationParams

# Initialize the router
router = LLMRouter()

# Simple generation
response = await router.generate(
    messages="What is the capital of France?",
    llm_model_id="GPT-4o Mini",
    raw_params={"temperature": 0.7, "max_tokens": 100}
)
print(response.text)

# Conversation support
from steer_llm_sdk import ConversationMessage, ConversationRole

messages = [
    ConversationMessage(role=ConversationRole.SYSTEM, content="You are a helpful assistant."),
    ConversationMessage(role=ConversationRole.USER, content="What is Python?")
]

response = await router.generate(
    messages=messages,
    llm_model_id="Claude 3.5 Sonnet",
    raw_params={"temperature": 0.5}
)
```

## Streaming Example

```python
# Stream responses
async for chunk in router.generate_stream(
    messages="Write a short story about a robot",
    llm_model_id="GPT-4o Mini",
    raw_params={"temperature": 0.8}
):
    print(chunk, end="", flush=True)
```

## Available Models

```python
from steer_llm_sdk import get_available_models

# List all available models
models = get_available_models()
for model_id, config in models.items():
    print(f"{model_id}: {config.provider} - {config.description}")
```

## Configuration

Set up your API keys as environment variables:

```bash
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
export XAI_API_KEY="your-xai-key"
```

## Advanced Usage

### Custom Parameters

```python
from steer_llm_sdk import normalize_params, get_config

# Get model configuration
config = get_config("GPT-4o Mini")

# Normalize parameters for the model
params = normalize_params({
    "temperature": 0.9,
    "max_tokens": 500,
    "top_p": 0.95
}, config)
```

### Cost Calculation

```python
from steer_llm_sdk import calculate_cost, get_config

# After generation
usage = {"prompt_tokens": 100, "completion_tokens": 50}
config = get_config("GPT-4o Mini")
cost = calculate_cost(usage, config)
print(f"Generation cost: ${cost:.4f}")
```

### Provider Status

```python
# Check provider availability
status = router.get_provider_status()
for provider, available in status.items():
    print(f"{provider}: {'✓' if available else '✗'}")
```

## API Reference

### Core Classes

- `LLMRouter`: Main router for handling LLM requests
- `GenerationParams`: Normalized generation parameters
- `GenerationResponse`: Standardized response format
- `ConversationMessage`: Message format for conversations
- `ModelConfig`: Model configuration schema

### Key Functions

- `get_config(llm_model_id)`: Get configuration for a specific model
- `get_available_models()`: List all enabled models
- `is_model_available(llm_model_id)`: Check if a model is available
- `normalize_params(raw_params, config)`: Normalize parameters
- `calculate_cost(usage, config)`: Calculate generation cost

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.