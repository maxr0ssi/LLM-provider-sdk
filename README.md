# LLM Provider SDK

**One SDK to rule them all.** I built this because I was tired of rewriting LLM integrations for every new project. This SDK is my solution - a single, reusable package that handles all the complexity of working with multiple LLM providers.

Write once, use everywhere. Any model, any provider, same clean interface.

## The Problem I Solved

Every time I started a new project that needed LLM capabilities, I faced the same challenges:
- Writing boilerplate code for each provider (OpenAI, Anthropic, xAI)
- Handling streaming differently for each provider's quirks  
- Rewriting retry logic and error handling
- Managing API keys and costs separately
- Building the same tool-calling patterns over and over

**This SDK is my answer:** A battle-tested, production-ready package that I can drop into any project and immediately have access to any LLM I want, with all the infrastructure already built.

## What This Gives You

- **Instant access** to GPT-4, Claude, Grok, and more - switch models with one parameter
- **Unified interface** - learn once, use with any provider
- **Production-ready** from day one - retries, circuit breakers, and error handling included
- **No more rewriting** - tools, agents, and streaming patterns ready to use

## Key Features

### 🔄 One Interface, All Providers
```python
# Same code works with any model
response = await client.generate("Explain AI", model="gpt-4o-mini")
response = await client.generate("Explain AI", model="claude-3-haiku-20240307")  
response = await client.generate("Explain AI", model="grok-3-mini")
```

### 🚀 Streaming That Just Works
- Unified streaming that handles each provider's quirks
- Consistent behavior across OpenAI, Anthropic, and xAI
- Built-in usage tracking and cost calculation

### 🔧 Build Complex Workflows Once
- Sequential tool calling for multi-step operations
- Agent infrastructure with OpenAI Agents SDK
- Reusable patterns for common tasks

### 💰 Track Everything Automatically
- Real-time cost calculation across all providers
- Token usage tracking with cache awareness
- Configurable pricing overrides

### 🛡️ Production-Ready Infrastructure
- Circuit breakers per provider
- Intelligent retry with exponential backoff
- Idempotency support for safe retries
- Comprehensive error handling

### 📊 Built-in Observability
- Metrics collection and tracing
- Performance monitoring
- Pluggable sinks for any monitoring system

## Requirements

- Python 3.11+ (3.10 not supported because pipe operators > Optional[T])

## Installation

```bash
# Basic installation
pip install git+https://github.com/maxr0ssi/LLM-provider-sdk.git

# With agent support
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git#egg=steer-llm-sdk[openai-agents]"

# With everything
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git#egg=steer-llm-sdk[openai-agents,tiktoken,http]"
```

## Quick Start

### Initialize Once, Use Everywhere

```python
from steer_llm_sdk import SteerLLMClient

# Set up your client with all your API keys
client = SteerLLMClient(
    openai_api_key="your-openai-key",
    anthropic_api_key="your-anthropic-key",
    xai_api_key="your-xai-key"
)
```

### Generate Text with Any Model

```python
# Pick any model - the interface stays the same
response = await client.generate(
    "Write a haiku about programming",
    model="gpt-4o-mini"  # or "claude-3-haiku-20240307" or "grok-3-mini"
)
print(response.text)
print(f"Cost: ${response.cost_usd:.6f}")
```

### Stream Responses Consistently

```python
# Streaming works the same way for all providers
async for chunk in client.stream(
    "Tell me about the future of AI",
    model="claude-3-5-sonnet-20241022"
):
    print(chunk, end="", flush=True)

# Or get usage data with your stream
response = await client.stream_with_usage(
    "Generate a business plan outline",
    model="gpt-4o-mini"
)
print(f"\nTotal tokens: {response.usage['total_tokens']}")
print(f"Cost: ${response.cost_usd:.6f}")
```

### Build Reusable Tools

```python
from steer_llm_sdk.orchestration import Tool, Orchestrator

# Define a tool once, use it in any project
class AnalysisTool(Tool):
    @property
    def name(self):
        return "analyze_data"
    
    async def execute(self, request, options=None, event_manager=None):
        # Your tool logic here
        result = await analyze_data(request["data"])
        return {"analysis": result}

# Register and use
client.register_tool(AnalysisTool())
orchestrator = Orchestrator()
result = await orchestrator.run(
    request={"data": your_data},
    tool_name="analyze_data"
)
```

### Create Agents with Tools

```python
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition, Tool
from steer_llm_sdk.agents.runner import AgentRunner

# Define reusable agent patterns
def calculate_metrics(data: list) -> dict:
    """Calculate statistics from data."""
    return {
        "mean": sum(data) / len(data),
        "max": max(data),
        "min": min(data)
    }

definition = AgentDefinition(
    system="You are a data analysis assistant.",
    user_template="Analyze this data: {data}",
    model="gpt-4",
    tools=[
        Tool(
            name="calculate_metrics",
            description="Calculate statistics from numerical data",
            parameters={
                "type": "object",
                "properties": {
                    "data": {"type": "array", "items": {"type": "number"}}
                },
                "required": ["data"]
            },
            handler=calculate_metrics
        )
    ]
)

# Run with any compatible model
runner = AgentRunner()
result = await runner.run(
    definition=definition,
    variables={"data": [1, 2, 3, 4, 5]}
)
```

## Architecture

Clean, layered architecture that's easy to extend:

```
┌─────────────────────────────────────────────────────────┐
│                 Your Application                         │
├─────────────────────────────────────────────────────────┤
│              SteerLLMClient (Unified API)                │
├─────────────────────────────────────────────────────────┤
│     Streaming Layer (Normalizes all providers)          │
├─────────────────────────────────────────────────────────┤
│    Reliability Layer (Retries, Circuit Breakers)        │
├─────────────────────────────────────────────────────────┤
│        Provider Adapters (OpenAI, Anthropic, xAI)       │
└─────────────────────────────────────────────────────────┘
```

## Why This SDK?

I use this in all my projects now. It's saved me countless hours of rewriting the same integration code. Here's what it solves:

- **No more provider lock-in**: Switch between models with one line
- **Consistent streaming**: Finally, streaming that works the same everywhere
- **Reusable patterns**: Build your tools once, use them anywhere
- **Cost visibility**: Know what you're spending across all providers
- **Production-ready**: All the boring stuff (retries, errors, monitoring) is handled

## Real-World Usage

### Multi-Model Comparison
```python
models = ["gpt-4o-mini", "claude-3-haiku-20240307", "grok-3-mini"]
prompt = "Explain quantum computing to a 5-year-old"

for model in models:
    response = await client.generate(prompt, model)
    print(f"\n{model}: {response.text[:200]}...")
    print(f"Cost: ${response.cost_usd:.6f}")
```

### Reliable Document Processing
```python
# The SDK handles retries and failures automatically
async def process_document(doc):
    try:
        # If one provider fails, it automatically retries
        result = await client.generate(
            f"Summarize this document: {doc}",
            model="gpt-4o-mini",
            max_tokens=500
        )
        return result.text
    except Exception as e:
        # Only fails if all retries exhausted
        logger.error(f"Failed to process: {e}")
```

### Cost-Aware Operations
```python
# Set a cost budget and track usage
budget = 1.00  # $1 budget
total_cost = 0

while total_cost < budget:
    response = await client.generate(
        "Generate a creative story idea",
        model="gpt-4o-mini"
    )
    total_cost += response.cost_usd
    print(f"Generated idea (${response.cost_usd:.6f})")
    print(f"Budget remaining: ${budget - total_cost:.2f}")
```

### Advanced Orchestration with Budgets
```python
# Use orchestration for complex operations with budgets and reliability
from steer_llm_sdk.orchestration import Orchestrator, OrchestrationConfig

orchestrator = Orchestrator()
result = await orchestrator.run(
    request={"data": "quarterly sales data", "analysis_type": "trends"},
    tool_name="analysis_bundle",
    tool_options={
        "k": 3,  # Run 3 parallel analyses
        "model": "gpt-4o-mini"
    },
    options=OrchestrationConfig(
        # Budget constraints
        budget={
            "tokens": 5000,      # Max 5k tokens total
            "cost_usd": 0.50,    # Max $0.50 spend
            "ms": 30000          # 30 second timeout
        },
        # Reliability settings
        max_retries=2,
        retry_on_failure=True,
        enable_circuit_breaker=True,
        # Execution settings
        max_parallel=5,
        deterministic=True
    )
)

print(f"Analysis complete. Total cost: ${result.usage.get('cost_usd', 0):.6f}")
```

## Documentation

- [Streaming Guide](docs/guides/streaming.md) - Master streaming patterns
- [Agent Development](docs/guides/agent-runtime-integration.md) - Build sophisticated agents
- [Orchestration Guide](docs/orchestration/) - Complex multi-step workflows
- [Architecture Overview](docs/architecture/) - How it all fits together

## License

GPL-3.0 - see [LICENSE](LICENSE). This ensures the SDK remains open and improvements benefit everyone.

---

*Built because I needed it. Shared because you might need it too.*

**Created by Max Rossi** | [GitHub](https://github.com/maxr0ssi)