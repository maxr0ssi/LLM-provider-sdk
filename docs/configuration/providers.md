# Provider Configuration

This guide covers provider-specific configuration for the Steer LLM SDK.

## Provider Setup

### OpenAI

```python
# Environment variables
export OPENAI_API_KEY="sk-..."
export OPENAI_ORG_ID="org-..."  # Optional

# Custom base URL (for proxies or compatible APIs)
export OPENAI_API_BASE="https://api.openai.com/v1"
```

### Anthropic

```python
# Environment variables
export ANTHROPIC_API_KEY="sk-ant-..."

# Custom settings
export ANTHROPIC_MAX_RETRIES="3"
export ANTHROPIC_TIMEOUT="300"  # seconds
```

### xAI (Grok)

```python
# Environment variables
export XAI_API_KEY="xai-..."
export XAI_BASE_URL="https://api.x.ai/v1"
```

## Model Configuration

### Available Models

```python
from steer_llm_sdk.core.routing import get_available_models

# List all available models
models = get_available_models()
for model in models:
    print(f"{model['model_id']}: {model['provider']} - {model['context_length']} tokens")
```

### Model Capabilities

```python
from steer_llm_sdk.core.routing import get_config

# Check model capabilities
config = get_config("gpt-4")
print(f"Supports JSON: {config.supports_json_schema}")
print(f"Supports streaming: {config.supports_streaming}")
print(f"Max tokens: {config.max_tokens}")
print(f"Temperature range: {config.min_temperature}-{config.max_temperature}")
```

### Custom Model Registration

```python
from steer_llm_sdk.core.capabilities import MODEL_CAPABILITIES, ProviderCapabilities
from steer_llm_sdk.models.generation import ProviderType

# Add a custom model
MODEL_CAPABILITIES["custom-model"] = ProviderCapabilities(
    provider=ProviderType.OPENAI,  # Use OpenAI adapter
    supports_streaming=True,
    supports_json_schema=True,
    supports_tool_calls=False,
    supports_image_input=False,
    supports_video_input=False,
    supports_seed=True,
    supports_temperature=True,
    fixed_temperature=None,
    min_temperature=0.0,
    max_temperature=2.0,
    uses_max_completion_tokens=False,
    supports_prompt_caching=False,
    context_length=8192,
    max_tokens=4096,
    pricing_per_million_input_tokens=10.0,
    pricing_per_million_output_tokens=30.0
)
```

## Provider-Specific Features

### OpenAI Responses API

```python
# Models that support Responses API
RESPONSES_API_MODELS = ["gpt-4.1-mini", "gpt-5-mini"]

# Enable Responses API features
response = await client.generate(
    messages="Extract data",
    model="gpt-4.1-mini",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "output",
            "schema": {...},
            "strict": True
        }
    }
)
```

### Anthropic Prompt Caching

```python
# Models with prompt caching
CACHE_ENABLED_MODELS = ["claude-3-opus", "claude-3-sonnet", "claude-3.5-sonnet"]

# Cache will be used automatically for supported models
response = await client.generate(
    messages=[
        {"role": "system", "content": "Long system prompt..."},  # Will be cached
        {"role": "user", "content": "Short question"}
    ],
    model="claude-3-opus"
)
```

### xAI Specific Settings

```python
# xAI uses a two-step process
# No special configuration needed - handled automatically by the adapter
```

## Advanced Provider Configuration

### Custom Headers

```python
import os

# Add custom headers for all requests to a provider
os.environ["OPENAI_DEFAULT_HEADERS"] = '{"X-Custom-Header": "value"}'
```

### Proxy Configuration

```python
# HTTP proxy
export HTTP_PROXY="http://proxy.company.com:8080"
export HTTPS_PROXY="http://proxy.company.com:8080"

# Provider-specific proxy
export OPENAI_PROXY="http://openai-proxy.company.com:8080"
```

### Timeout Configuration

```python
# Global timeout
export LLM_REQUEST_TIMEOUT="60"  # seconds

# Provider-specific timeouts
export OPENAI_TIMEOUT="30"
export ANTHROPIC_TIMEOUT="60"
export XAI_TIMEOUT="45"
```

## Provider Fallbacks

```python
from steer_llm_sdk.core.routing import LLMRouter

class CustomRouter(LLMRouter):
    """Router with fallback configuration."""
    
    def __init__(self):
        super().__init__()
        
        # Define fallback chains
        self.fallback_chains = {
            "gpt-4": ["gpt-4", "gpt-3.5-turbo", "claude-3-opus"],
            "claude-3-opus": ["claude-3-opus", "claude-3-sonnet", "gpt-4"],
            "grok-1": ["grok-1", "gpt-4", "claude-3-opus"]
        }
    
    async def generate_with_fallback(self, messages, preferred_model, **kwargs):
        """Try preferred model, fall back if needed."""
        chain = self.fallback_chains.get(preferred_model, [preferred_model])
        
        for model in chain:
            try:
                return await self.generate(messages, model, kwargs)
            except Exception as e:
                if model == chain[-1]:  # Last model in chain
                    raise
                print(f"Model {model} failed, trying next: {e}")
```

## Rate Limiting Configuration

```python
# Per-provider rate limits
RATE_LIMITS = {
    "openai": {
        "requests_per_minute": 3500,
        "tokens_per_minute": 90000
    },
    "anthropic": {
        "requests_per_minute": 1000,
        "tokens_per_minute": 100000
    },
    "xai": {
        "requests_per_minute": 60,
        "tokens_per_minute": 10000
    }
}

# Configure in environment
export OPENAI_RPM_LIMIT="3500"
export OPENAI_TPM_LIMIT="90000"
```

## Testing Provider Configuration

```python
async def test_provider_config(provider: str):
    """Test provider configuration."""
    from steer_llm_sdk import SteerLLMClient
    
    client = SteerLLMClient()
    
    # Get a model for this provider
    models = get_available_models()
    provider_models = [m for m in models if m["provider"] == provider]
    
    if not provider_models:
        print(f"No models available for {provider}")
        return False
    
    model = provider_models[0]["model_id"]
    
    try:
        # Simple test
        response = await client.generate(
            messages="Say 'test successful'",
            model=model,
            max_tokens=10
        )
        print(f"{provider} configuration OK: {response}")
        return True
        
    except Exception as e:
        print(f"{provider} configuration FAILED: {e}")
        return False

# Test all providers
for provider in ["openai", "anthropic", "xai"]:
    await test_provider_config(provider)
```

## Environment Variable Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key | Required |
| `XAI_API_KEY` | xAI API key | Required |
| `OPENAI_API_BASE` | OpenAI base URL | https://api.openai.com/v1 |
| `ANTHROPIC_API_BASE` | Anthropic base URL | https://api.anthropic.com |
| `XAI_BASE_URL` | xAI base URL | https://api.x.ai/v1 |
| `DEFAULT_PROVIDER` | Default provider | openai |
| `DEFAULT_MODEL` | Default model | gpt-4o-mini |
| `LLM_REQUEST_TIMEOUT` | Global timeout (seconds) | 60 |

## Troubleshooting

### API Key Issues

```python
# Check if API keys are loaded
import os

for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY"]:
    if key in os.environ:
        print(f"{key}: {'*' * 8}{os.environ[key][-4:]}")
    else:
        print(f"{key}: NOT SET")
```

### Connection Issues

```python
# Test provider connectivity
import httpx

async def test_connectivity(base_url: str):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(base_url, timeout=5.0)
            print(f"{base_url}: {response.status_code}")
        except Exception as e:
            print(f"{base_url}: FAILED - {e}")

# Test each provider
await test_connectivity("https://api.openai.com")
await test_connectivity("https://api.anthropic.com")
await test_connectivity("https://api.x.ai")
```