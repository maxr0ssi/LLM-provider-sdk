# Steer LLM SDK

A unified Python SDK for integrating multiple Large Language Model (LLM) providers (OpenAI, Anthropic, xAI) with a consistent interface, intelligent routing, and comprehensive model management.

## Overview

The Steer LLM SDK is the foundational AI integration layer for the Steer ecosystem. It provides:

- **Unified Interface**: Single API for multiple LLM providers
- **Intelligent Routing**: Automatic provider selection based on model availability
- **Model Registry**: Centralized configuration for all supported models
- **Cost Tracking**: Built-in usage and cost calculation
- **Async Support**: Full async/await support for all operations
- **Streaming**: Real-time streaming responses
- **Conversation Management**: Native support for multi-turn conversations

## Role in Steer Ecosystem

This SDK serves as the core LLM abstraction layer for all Steer products and services:

- **Steer Platform**: Powers all AI features in the main application
- **Control Game**: Provides LLM capabilities for game mechanics and AI agents
- **Future Services**: Foundation for any AI-powered features across Steer products

By centralizing LLM interactions, we ensure:
- Consistent AI behavior across all products
- Simplified provider management and switching
- Unified cost tracking and optimization
- Single point of updates for new models and providers

> Nexus Integration Brief: The Nexus agent‑mesh docs now live in this repo under `docs/nexus/`. The SDK’s role is SDK‑only plumbing for agents: Responses API mapping (GPT‑5 mini preferred), structured outputs via JSON schema, optional streaming, optional local deterministic tool hooks, determinism/idempotency, and metrics. See `docs/nexus/sdk-deliverables.md` for concrete deliverables and `docs/nexus/agent-sdk-guide.md` for usage patterns.

## Installation

### Requirements
- Python 3.10 or higher
- API keys for the providers you want to use

### Install from Private PyPI
```bash
pip install --index-url http://your-pypi-server/simple/ steer-llm-sdk
```

### Install from Source
```bash
git clone https://github.com/steer-ai/steer-llm-sdk.git
cd steer-llm-sdk
pip install -e .
```

## Configuration

Set your API keys as environment variables:

```bash
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
export XAI_API_KEY="your-xai-key"
```

Or use a `.env` file:
```env
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
XAI_API_KEY=your-xai-key
```

## Quick Start

### Basic Usage

```python
from steer_llm_sdk import generate

# Simple generation (async)
response = await generate(
    "Explain quantum computing in simple terms",
    "gpt-4o-mini"
)
print(response)
```

### Using the Client

```python
from steer_llm_sdk import SteerLLMClient

# Create client
client = SteerLLMClient()

# Generate text
response = await client.generate(
    "Write a haiku about programming",
    "claude-3-haiku-20240307"
)

# Stream responses
async for chunk in client.stream(
    "Tell me a story",
    "gpt-4o-mini"
):
    print(chunk, end="")

# Stream with usage data (NEW!)
response = await client.stream(
    "Explain Python in one sentence",
    "gpt-4o-mini",
    return_usage=True
)
print(f"Response: {response.get_text()}")
print(f"Tokens used: {response.usage['total_tokens']}")
print(f"Cost: ${response.cost_usd:.6f}")
```

### Conversation Support

```python
from steer_llm_sdk import SteerLLMClient, ConversationMessage, ConversationRole

client = SteerLLMClient()

# Multi-turn conversation
messages = [
    ConversationMessage(
        role=ConversationRole.SYSTEM,
        content="You are a helpful assistant"
    ),
    ConversationMessage(
        role=ConversationRole.USER,
        content="What's the capital of France?"
    )
]

response = await client.generate(messages, "gpt-4o-mini")
```

### Model Discovery

```python
from steer_llm_sdk import get_available_models

# Get all available models
models = get_available_models()

for model_id, config in models.items():
    print(f"{model_id}: {config.description}")
    print(f"  Provider: {config.provider}")
    print(f"  Max tokens: {config.max_tokens}")
    print(f"  Cost per 1k tokens: ${config.cost_per_1k_tokens}")
```

## Supported Models

### OpenAI
- **GPT-4o Mini** (`gpt-4o-mini`) - Efficient, cost-effective model
- **GPT-4.1 Nano** (`gpt-4.1-nano`) - Ultra-light model for simple tasks
- **GPT-3.5 Turbo** (`gpt-3.5-turbo`) - Fast general-purpose model

### Anthropic
- **Claude 3 Haiku** (`claude-3-haiku-20240307`) - Fast and affordable
- **Claude 3.5 Sonnet** (`claude-3-5-sonnet-20241022`) - Balanced performance
- **Claude 3 Opus** (`claude-3-opus-20240229`) - Most capable model

### xAI
- **Grok Beta** (`grok-beta`) - Early access model
- **Grok 2** (`grok-2-1212`) - Latest production model
- **Grok 3 Mini** (`grok-3-mini`) - Lightweight variant

## Advanced Features

### Custom Parameters

```python
response = await client.generate(
    "Generate creative ideas",
    "gpt-4o-mini",
    temperature=0.9,
    max_tokens=500,
    top_p=0.95
)
```

### Cost Calculation

```python
response = await client.generate("Hello world", "gpt-4o-mini")
print(f"Cost: ${response.cost_usd:.4f}")
print(f"Tokens used: {response.usage}")
```

### Model Availability Check

```python
from steer_llm_sdk import check_lightweight_availability

if check_lightweight_availability("gpt-4o-mini"):
    response = await generate("Hello", "gpt-4o-mini")
else:
    print("Model not available")
```

### Direct Router Usage

```python
from steer_llm_sdk import llm_router

# For more control, use the router directly
response = await llm_router.generate(
    messages="Translate to French: Hello world",
    llm_model_id="gpt-4o-mini",
    raw_params={"temperature": 0.3}
)
```

### Streaming with Usage Data (NEW!)

The SDK now supports getting token usage and cost information from streaming responses:

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

# Enable usage data collection with return_usage=True
response = await client.stream(
    messages="Write a Python function to calculate factorial",
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=200,
    return_usage=True  # New parameter!
)

# Access the complete response text
print("Generated code:")
print(response.get_text())

# Access usage information
print(f"\nToken usage:")
print(f"  Prompt tokens: {response.usage['prompt_tokens']}")
print(f"  Completion tokens: {response.usage['completion_tokens']}")
print(f"  Total tokens: {response.usage['total_tokens']}")

# Access cost information (when available)
if response.cost_usd:
    print(f"\nEstimated cost: ${response.cost_usd:.6f}")
    if response.cost_breakdown:
        print(f"  Input cost: ${response.cost_breakdown['input_cost']:.6f}")
        print(f"  Output cost: ${response.cost_breakdown['output_cost']:.6f}")

# You can also iterate over the collected chunks
for i, chunk in enumerate(response.chunks):
    print(f"Chunk {i}: {chunk}")
```

**Backwards Compatibility**: The default behavior remains unchanged. When `return_usage=False` (default), the stream method yields string chunks as before:

```python
# Traditional streaming (unchanged)
async for chunk in client.stream(messages="Hello", model="gpt-4o-mini"):
    print(chunk, end="")
```

## Architecture

The SDK follows a modular architecture:

```
steer_llm_sdk/
├── __init__.py          # Public API exports
├── main.py              # Client implementation
├── cli.py               # Command-line interface
├── models/              # Data models and types
│   ├── generation.py    # Request/response models
│   └── conversation_types.py  # Conversation support
├── llm/
│   ├── providers/       # Provider implementations
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   └── xai.py
│   ├── router.py        # Request routing logic
│   └── registry.py      # Model configuration
└── config/              # Configuration management
    └── models.py        # Model definitions
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/steer-ai/steer-llm-sdk.git
cd steer-llm-sdk

# Create virtual environment (Python 3.10+)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=steer_llm_sdk

# Run specific test file
pytest tests/unit/test_providers.py
```

### Code Quality

```bash
# Format code
black steer_llm_sdk tests

# Lint code
ruff check steer_llm_sdk tests
```

## API Reference

### Client Methods

- `generate(messages, model, **params)`: Generate text response
- `stream(messages, model, return_usage=False, **params)`: Stream text response
  - `return_usage=False` (default): Yields string chunks for backwards compatibility
  - `return_usage=True`: Returns a `StreamingResponseWithUsage` object with usage data
- `get_available_models()`: Get all configured models
- `check_model_availability(model_id)`: Check if model is available

### Parameters

- `messages`: String or list of ConversationMessage objects
- `model`: Model ID string (e.g., "gpt-4o-mini")
- `temperature`: Controls randomness (0.0-2.0)
- `max_tokens`: Maximum tokens to generate
- `top_p`: Nucleus sampling parameter
- `frequency_penalty`: Reduce repetition
- `presence_penalty`: Encourage new topics

## Error Handling

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

try:
    response = await client.generate("Hello", "gpt-4o-mini")
except Exception as e:
    print(f"Error: {e}")
```

## Performance Considerations

- Models are loaded on-demand to minimize memory usage
- Streaming is recommended for long responses
- Use `check_lightweight_availability()` for quick availability checks
- Cost calculation adds minimal overhead

## Security

- API keys are never logged or stored
- All provider communications use HTTPS
- No user data is retained by the SDK
- Supports custom HTTP proxies if needed

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary software. All rights reserved by Steer AI.

## Support

For issues and questions:
- Create an issue on GitHub
- Contact the Steer team at support@steer.ai

## Changelog

### v0.1.0 (2024-06-28)
- Initial release
- Support for OpenAI, Anthropic, and xAI providers
- Unified interface with streaming support
- Cost calculation and model registry
- Python 3.10+ requirement
- Full async/await support
- Comprehensive test coverage