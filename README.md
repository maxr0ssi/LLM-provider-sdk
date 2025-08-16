# Steer LLM SDK

A unified Python SDK for integrating multiple Large Language Model (LLM) providers (OpenAI, Anthropic, xAI) with a consistent interface, intelligent routing, and comprehensive model management.

## Overview
### Streaming API (Updated)

We have split the streaming API to provide a clean, scalable contract:

- `SteerLLMClient.stream(...)` is a pure async generator that yields text chunks. It no longer accepts `return_usage`.
- `SteerLLMClient.stream_with_usage(...)` is an awaitable that returns a wrapper with full text and usage metadata after streaming completes.
- `SteerLLMClient.generate(...)` returns a `GenerationResponse` object.
- Convenience function `steer_llm_sdk.api.client.generate(...)` returns just the generated text (`str`).

#### Quick examples

Async generator streaming (preferred for high-throughput):

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()
async for chunk in client.stream("Hello", model="gpt-4o-mini", max_tokens=64):
    print(chunk, end="")
```

Awaitable streaming with usage summary:

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()
resp = await client.stream_with_usage(
    messages="Tell a 10-word joke",
    model="gpt-4o-mini",
    max_tokens=64,
)

print(resp.get_text())
print(resp.usage)  # {prompt_tokens, completion_tokens, total_tokens, cache_info}
```

Object vs. text responses:

```python
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.api.client import generate as text_generate

client = SteerLLMClient()
obj = await client.generate("Hello", model="gpt-4o-mini")  # GenerationResponse
print(obj.text)

txt = await text_generate("Hello", model="gpt-4o-mini")   # str
print(txt)
```

### Migration notes (Return type and streaming split)

If you previously used `stream(..., return_usage=True)`, migrate to `stream_with_usage(...)`.

Before:

```python
response = await client.stream("Hello", model="gpt-4o-mini", return_usage=True)
print(response.get_text())
print(response.usage)
```

After:

```python
response = await client.stream_with_usage("Hello", model="gpt-4o-mini")
print(response.get_text())
print(response.usage)
```

If you previously expected `str` from `client.generate(...)`, switch to the convenience function or use `.text`:

Before:

```python
txt = await client.generate("Hello")  # str
```

After (Option A – convenience):

```python
from steer_llm_sdk.api.client import generate
txt = await generate("Hello")  # str
```

After (Option B – object):

```python
obj = await client.generate("Hello")  # GenerationResponse
txt = obj.text
```

Deprecation timeline:

- Passing `return_usage` to `stream(...)` is deprecated and will raise in a future minor release.
- Use `stream_with_usage(...)` immediately for usage summaries.


The Steer LLM SDK is the foundational AI integration layer for the Steer ecosystem. It provides:

- **Unified Interface**: Single API for multiple LLM providers
- **Intelligent Routing**: Automatic provider selection based on model availability
- **Model Registry**: Centralized configuration for all supported models
- **Cost Tracking**: Built-in usage and cost calculation
- **Async Support**: Full async/await support for all operations
- **Streaming**: Real-time streaming responses
- **Conversation Management**: Native support for multi-turn conversations
- **Agent Runtime**: Native OpenAI Agents SDK integration with tools and structured outputs

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

### Install from GitHub (Recommended)
```bash
# Install base SDK
pip install git+https://github.com/maxr0ssi/LLM-provider-sdk.git@main

# Install with OpenAI Agents SDK support (for agent runtime features)
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git@main#egg=steer-llm-sdk[openai-agents]"

# Install with token counting support
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git@main#egg=steer-llm-sdk[tiktoken]"

# Install with all optional dependencies
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git@main#egg=steer-llm-sdk[openai-agents,tiktoken]"

# Or install a specific version/tag
pip install git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.2.1
```

### Install from Source (Development)
```bash
git clone https://github.com/maxr0ssi/LLM-provider-sdk.git
cd LLM-provider-sdk
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
    if config.input_cost_per_1k_tokens and config.output_cost_per_1k_tokens:
        print(f"  Input cost: ${config.input_cost_per_1k_tokens}/1k tokens")
        print(f"  Output cost: ${config.output_cost_per_1k_tokens}/1k tokens")
```

### Pricing Configuration

Model pricing is configured in `steer_llm_sdk/config/models.py`. You can override pricing using:

#### Environment Variable (JSON)
```bash
export STEER_PRICING_OVERRIDES_JSON='{
  "gpt-4o-mini": {
    "input_cost_per_1k_tokens": 0.00015,
    "output_cost_per_1k_tokens": 0.0006
  }
}'
```

#### Configuration File
```bash
export STEER_PRICING_OVERRIDES_FILE=/path/to/pricing.json
# Or place in ~/.steer/pricing_overrides.json
```

#### File Format
```json
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

The SDK automatically calculates costs based on token usage and model pricing:

```python
response = await client.generate("Hello world", "gpt-4o-mini")
print(f"Cost: ${response.cost_usd:.4f}")
print(f"Cost breakdown: {response.cost_breakdown}")
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

### Streaming with Usage Data (new split API)

To capture usage and cost alongside streamed text, use the split API:

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

# Pure streaming (yields chunks)
async for chunk in client.stream(
    messages="Write a Python function to calculate factorial",
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=200,
):
    print(chunk, end="")

# Streaming with usage summary (awaitable)
response = await client.stream_with_usage(
    messages="Write a Python function to calculate factorial",
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=200,
)

print("\nGenerated code:")
print(response.get_text())

print(f"\nToken usage:")
print(f"  Prompt tokens: {response.usage['prompt_tokens']}")
print(f"  Completion tokens: {response.usage['completion_tokens']}")
print(f"  Total tokens: {response.usage['total_tokens']}")

if response.cost_usd:
    print(f"\nEstimated cost: ${response.cost_usd:.6f}")
    if response.cost_breakdown:
        print(f"  Input cost: ${response.cost_breakdown['input_cost']:.6f}")
        print(f"  Output cost: ${response.cost_breakdown['output_cost']:.6f}")
```

### Agent Runtime (OpenAI Agents SDK)

The SDK now includes native support for the OpenAI Agents SDK, enabling advanced agent capabilities with tools and structured outputs. 

**Installation**: Requires the `openai-agents` extra:
```bash
pip install "steer-llm-sdk[openai-agents]"
```

**Basic Agent Example**:
```python
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition, Tool
from steer_llm_sdk.agents.runner import AgentRunner

# Define a tool
def calculate_factorial(n: int) -> int:
    """Calculate the factorial of a number."""
    if n <= 1:
        return 1
    return n * calculate_factorial(n - 1)

# Create agent definition
definition = AgentDefinition(
    system="You are a helpful math assistant.",
    user_template="Calculate the factorial of {number}",
    model="gpt-4",
    tools=[
        Tool(
            name="factorial",
            description="Calculate the factorial of a number",
            parameters={
                "type": "object",
                "properties": {"n": {"type": "integer"}},
                "required": ["n"]
            },
            handler=calculate_factorial
        )
    ]
)

# Run the agent
runner = AgentRunner()
result = await runner.run(
    definition=definition,
    variables={"number": 5},
    options={"runtime": "openai_agents"}
)

print(result.content)  # "The factorial of 5 is 120"
```

**Structured Output with JSON Schema**:
```python
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition

# Define agent with structured output
definition = AgentDefinition(
    system="Extract product information from the description.",
    user_template="Product: {description}",
    model="gpt-4",
    json_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "price": {"type": "number"},
            "category": {"type": "string"}
        },
        "required": ["name", "price", "category"],
        "additionalProperties": False
    }
)

# Run with strict JSON validation
result = await runner.run(
    definition=definition,
    variables={"description": "iPhone 15 Pro, smartphone, $999"},
    options={"runtime": "openai_agents", "strict": True}
)

print(result.final_json)  # {"name": "iPhone 15 Pro", "price": 999, "category": "smartphone"}
```

**Streaming Agent Responses**:
```python
# Stream agent responses with tools
async for event in runner.stream(
    definition=definition,
    variables={"query": "Calculate 10!"},
    options={"runtime": "openai_agents"}
):
    if event.type == "delta":
        print(event.delta, end="")
    elif event.type == "tool_call":
        print(f"\n[Calling tool: {event.metadata['tool']}]")
```

For more details, see the [Agent Runtime Integration Guide](docs/guides/agent-runtime-integration.md).

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

- `generate(messages, model, **params)`: Generate text response (returns object)
- `stream(messages, model, **params)`: Stream text response (async generator yielding chunks)
- `stream_with_usage(messages, model, **params)`: Awaitable streaming with usage summary
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