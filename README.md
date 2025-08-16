# Steer LLM SDK

A production-ready Python SDK for integrating multiple Large Language Model (LLM) providers with enterprise-grade features including intelligent routing, unified streaming, agent infrastructure, and comprehensive observability.

## Key Features

- **🔄 Multi-Provider Support**: Seamless integration with OpenAI, Anthropic, and xAI
- **🚀 Unified Streaming**: Consolidated streaming architecture with consistent behavior across providers
- **🤖 Agent Infrastructure**: Native OpenAI Agents SDK integration with tools and structured outputs
- **💰 Cost Optimization**: Built-in pricing calculations with cache-aware billing
- **🛡️ Enterprise Reliability**: Circuit breakers, retry mechanisms, and idempotency support
- **📊 Observability**: Comprehensive metrics, tracing, and performance monitoring
- **⚡ High Performance**: Async-first design with connection pooling and streaming optimizations
- **🔧 Extensible**: Plugin architecture for custom providers and observability sinks

## Architecture Overview

The SDK implements a layered architecture designed for scalability and maintainability:

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│  (SteerLLMClient, Agent Runner, HTTP API)               │
├─────────────────────────────────────────────────────────┤
│                    Streaming Layer                       │
│  (StreamingHelper, EventProcessor, StreamAdapter)       │
├─────────────────────────────────────────────────────────┤
│                    Routing Layer                         │
│  (LLMRouter, Circuit Breakers, Retry Manager)          │
├─────────────────────────────────────────────────────────┤
│                    Provider Layer                        │
│  (OpenAI, Anthropic, xAI Adapters)                     │
└─────────────────────────────────────────────────────────┘
```

### Core Components

- **Routing Layer**: Intelligent request routing with circuit breakers and retry logic
- **Streaming Layer**: Unified streaming pipeline with event processing and normalization
- **Provider Layer**: Normalized interfaces for each LLM provider
- **Observability Layer**: Metrics collection, distributed tracing, and performance monitoring
- **Agent Layer**: Advanced agent capabilities with tool execution and structured outputs

## Overview

### API Key Configuration (v0.3.1+)

For improved security, API keys should be passed directly to the client instead of using environment variables:

```python
from steer_llm_sdk import SteerLLMClient

# Recommended: Pass API keys directly
client = SteerLLMClient(
    openai_api_key="your-openai-key",
    anthropic_api_key="your-anthropic-key", 
    xai_api_key="your-xai-key"
)

# Backward compatible: Use environment variables
# client = SteerLLMClient()  # Will read from OPENAI_API_KEY, etc.
```

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

### Install from GitHub Package Registry (Private Package)
```bash
# Configure GitHub authentication
export GITHUB_TOKEN=your_github_personal_access_token

# Install base SDK
pip install steer-llm-sdk --index-url https://${GITHUB_TOKEN}@github.com/maxr0ssi/LLM-provider-sdk/releases/download/v0.3.1/

# Or add to requirements.txt
--index-url https://${GITHUB_TOKEN}@github.com/maxr0ssi/LLM-provider-sdk/releases/download/v0.3.1/
steer-llm-sdk[openai-agents,tiktoken]
```

### Install from Source (Development)
```bash
# Install base SDK
pip install git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.1

# Install with OpenAI Agents SDK support (for agent runtime features)
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.1#egg=steer-llm-sdk[openai-agents]"

# Install with token counting support
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.1#egg=steer-llm-sdk[tiktoken]"

# Install with HTTP API endpoints (requires FastAPI)
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.1#egg=steer-llm-sdk[http]"

# Install with all optional dependencies
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.1#egg=steer-llm-sdk[openai-agents,tiktoken,http]"
```

### Local Development
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

### Streaming Configuration

The SDK provides comprehensive streaming configuration options:

```python
from steer_llm_sdk.models.streaming import StreamingOptions, JSON_MODE_OPTIONS

# Use preset configurations
response = await client.stream_with_usage(
    "Generate JSON data",
    model="gpt-4",
    response_format={"type": "json_object"},
    streaming_options=JSON_MODE_OPTIONS  # Optimized for JSON
)

# Or create custom options
options = StreamingOptions(
    enable_usage_aggregation=True,     # Track token usage
    enable_json_stream_handler=True,   # Handle JSON streaming
    connection_timeout=5.0,            # Connection timeout in seconds
    read_timeout=30.0,                 # Read timeout in seconds
    retry_on_connection_error=True,    # Retry on connection errors
    max_reconnect_attempts=3           # Maximum retry attempts
)
```

For detailed streaming configuration options, see the [Streaming Configuration Guide](docs/configuration/streaming.md).

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

# Stream with usage data
response = await client.stream_with_usage(
    "Explain Python in one sentence",
    "gpt-4o-mini"
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

## HTTP API Endpoints (Optional)

The SDK can optionally expose REST API endpoints using FastAPI:

```python
# Install with HTTP support
# pip install steer-llm-sdk[http]

from fastapi import FastAPI
from steer_llm_sdk.http.api import router as llm_router

app = FastAPI()
app.include_router(llm_router, prefix="/api/v1")

# Available endpoints:
# POST /api/v1/generate - Generate text
# POST /api/v1/stream - Stream text
# GET /api/v1/model-catalog - List models
# GET /api/v1/status - Check status
```

The SDK works perfectly without HTTP endpoints for notebooks, CLIs, and batch jobs. See the [HTTP Endpoints Guide](docs/guides/http-endpoints.md) for details.

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

The SDK follows a modular architecture with a unified streaming pipeline:

### Core Components

```
steer_llm_sdk/
├── api/                 # High-level client API
│   └── client.py        # SteerLLMClient implementation
├── core/                # Core functionality
│   ├── routing/         # Request routing and model selection
│   ├── capabilities/    # Model capabilities management
│   └── pricing/         # Pricing calculations
├── providers/           # Provider implementations
│   ├── base.py          # Base provider interface
│   ├── openai/          # OpenAI implementation
│   ├── anthropic/       # Anthropic implementation
│   └── xai/             # xAI implementation
├── streaming/           # Unified streaming architecture
│   ├── helpers.py       # StreamingHelper (orchestration)
│   ├── processor.py     # EventProcessor (pipeline)
│   ├── adapter.py       # StreamAdapter (normalization)
│   └── manager.py       # EventManager (callbacks)
├── models/              # Data models and types
│   ├── generation.py    # Request/response models
│   ├── events.py        # Streaming event types
│   └── streaming.py     # Streaming configuration
└── observability/       # Metrics and monitoring
    └── collector.py     # Metrics collection
```

### Streaming Architecture

The SDK uses a consolidated streaming architecture that ensures consistent behavior across all providers:

1. **StreamingHelper** - High-level orchestration of streaming operations
2. **EventProcessor** - Composable pipeline for filtering and transforming events  
3. **StreamAdapter** - Provider-specific normalization and event lifecycle

For detailed information, see the [Streaming Architecture documentation](docs/architecture/streaming.md).

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

## Documentation

- **[Architecture Overview](docs/architecture/)**: Detailed system design and components
- **[Streaming Guide](docs/guides/streaming.md)**: Complete streaming implementation guide
- **[Agent Development](docs/guides/agent-runtime-integration.md)**: Building agents with tools
- **[HTTP API Reference](docs/guides/http-endpoints.md)**: REST API endpoints documentation
- **[Configuration Guide](docs/configuration/)**: Provider and system configuration
- **[Metrics & Monitoring](docs/architecture/metrics.md)**: Observability setup

## Changelog

### v0.3.1 (2025-08)
- **Security**: API keys now passed directly to client instead of environment variables
- Backward compatible with environment variables

### v0.3.0 (2025-08)
- Agent infrastructure with OpenAI Agents SDK integration
- Unified streaming architecture consolidation
- Enhanced observability with metrics and tracing
- Circuit breakers and advanced retry mechanisms
- Responses API support for GPT-5 models
- Pre-release cleanup and optimization

### v0.2.x (2025-07)
- Layered architecture implementation (Phases 0-7)
- FastAPI separation into optional HTTP module
- Comprehensive pricing system overhaul
- Streaming API split (stream vs stream_with_usage)
- Performance optimizations and connection pooling

### v0.1.0 (2024-06-28)
- Initial release
- Support for OpenAI, Anthropic, and xAI providers
- Unified interface with streaming support
- Cost calculation and model registry
- Python 3.10+ requirement
- Full async/await support
- Comprehensive test coverage