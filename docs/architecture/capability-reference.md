# Model Capability Reference

This document provides a reference for all model capabilities in the SDK.

## Capability Flags

| Flag | Description | Impact |
|------|-------------|--------|
| `supports_json_schema` | Native JSON schema support | Enables Responses API for OpenAI |
| `supports_streaming` | Streaming response support | Enables stream() methods |
| `supports_tools` | Tool/function calling support | Enables tool use |
| `supports_seed` | Deterministic seed support | Enables reproducible outputs |
| `supports_temperature` | Temperature parameter support | Controls randomness |
| `requires_temperature_one` | Requires temperature=1.0 | Forces temperature to 1.0 |
| `uses_max_completion_tokens` | Uses max_completion_tokens | Maps max_tokens differently |
| `uses_max_output_tokens_in_responses_api` | Responses API uses max_output_tokens | Special handling for Responses API |
| `supports_prompt_caching` | Prompt caching support | Enables cache_control markers |
| `has_cached_pricing` | Has cached token pricing | Enables cache cost calculation |

## Model Capabilities Summary

### OpenAI Models

| Model | Temperature | Max Tokens Field (Chat) | Responses API Field | JSON Schema | Caching | Special Notes |
|-------|-------------|-------------------------|---------------------|-------------|---------|---------------|
| gpt-4o-mini | Normal | max_tokens | max_output_tokens | Yes | Yes | Standard model |
| gpt-4.1-nano | Normal | max_tokens | max_output_tokens | Yes | No | Budget model |
| gpt-3.5-turbo | Normal | max_tokens | - | No | No | Legacy model |
| o4-mini | Force 1.0 | max_completion_tokens | max_output_tokens | Yes | Yes | Requires temp=1.0 |
| gpt-4.1-mini | Normal | max_tokens | max_output_tokens | Yes | Yes | Standard model |
| gpt-5-mini | No (omit in Responses API) | max_tokens | max_output_tokens | Yes | Yes | No temp in Responses API |
| gpt-4o | Normal | max_tokens | max_output_tokens | Yes | Yes | Flagship model |
| gpt-4.1 | Normal | max_tokens | max_output_tokens | Yes | Yes | Flagship model |
| gpt-5 | Normal | max_tokens | max_output_tokens | Yes | Yes | Next-gen flagship |
| gpt-5-nano | Normal | max_tokens | max_output_tokens | Yes | Yes | Next-gen budget |

### Anthropic Models

| Model | Temperature | Max Tokens Field (Chat) | Responses API Field | JSON Schema | Caching | Special Notes |
|-------|-------------|-------------------------|---------------------|-------------|---------|---------------|
| claude-3-haiku-20240307 | Normal | max_tokens | - | No | Yes | Fast, affordable |
| claude-3-5-sonnet-20241022 | Normal | max_tokens | - | No | Yes | Balanced model |
| claude-3-opus-20240229 | Normal | max_tokens | - | No | Yes | Most capable |

### xAI Models

| Model | Temperature | Max Tokens Field (Chat) | Responses API Field | JSON Schema | Caching | Special Notes |
|-------|-------------|-------------------------|---------------------|-------------|---------|---------------|
| grok-beta | Normal | max_tokens | - | No | No | Early access |
| grok-2-1212 | Normal | max_tokens | - | No | No | Production model |
| grok-3-mini | Normal | max_tokens | - | No | No | Lightweight variant |

## Usage Examples

### Checking Temperature Support

```python
from steer_llm_sdk.core.capabilities import get_capabilities_for_model

caps = get_capabilities_for_model("gpt-5-mini")
if not caps.supports_temperature:
    print("Temperature parameter will be omitted for this model")
```

### Determining Max Tokens Field

```python
from steer_llm_sdk.core.capabilities import map_max_tokens_field

caps = get_capabilities_for_model("o4-mini")
field_name = map_max_tokens_field(caps, "openai")
print(f"Use {field_name} for this model")  # max_completion_tokens
```

### Applying Temperature Policy

```python
from steer_llm_sdk.core.capabilities import apply_temperature_policy

caps = get_capabilities_for_model("o4-mini")
params = {"temperature": 0.5}
params = apply_temperature_policy(params, caps)
print(params["temperature"])  # 1.0 (forced)
```

## Policy Helpers

The SDK provides several policy helper functions in `steer_llm_sdk.core.capabilities.policy`:

- `map_max_tokens_field()`: Determines correct max tokens parameter name
- `apply_temperature_policy()`: Applies temperature rules based on capabilities
- `format_responses_api_schema()`: Formats JSON schema for Responses API
- `should_use_responses_api()`: Determines if Responses API should be used
- `get_deterministic_settings()`: Gets deterministic parameters for a model
- `supports_prompt_caching()`: Checks if prompt caching is available
- `get_cache_control_config()`: Gets cache control configuration

## Adding New Models

When adding a new model:

1. Add capability definition to `MODEL_CAPABILITIES` in `core/capabilities/models.py`
2. Set all capability flags accurately based on provider documentation
3. Add pricing information to `config/models.py` if applicable
4. Test with the new model to ensure capabilities work correctly

No hardcoded model name checks should be added - all behavior should be driven by capabilities.