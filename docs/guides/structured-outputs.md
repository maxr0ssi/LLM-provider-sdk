# Structured Outputs Guide

Techniques for generating consistent, structured outputs from LLMs.

## Overview

Get deterministic, structured data from LLMs using:
- Temperature control and seeds for consistency
- JSON schemas for strict validation (Responses API)
- Structured output formats

## Deterministic Generation

### Temperature Control

Set temperature to 0 for the most deterministic output:

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

response = await client.generate(
    messages="Define artificial intelligence in exactly one sentence.",
    model="gpt-4",
    temperature=0.0,
    max_tokens=50
)
```

### Using Seeds

Models that support seed parameters provide additional reproducibility:

```python
# Same prompt + seed = same output
result1 = await client.generate(
    messages="Write a haiku about coding",
    model="gpt-5-mini",
    temperature=0,
    seed=42
)

result2 = await client.generate(
    messages="Write a haiku about coding",
    model="gpt-5-mini",
    temperature=0,
    seed=42
)

assert result1.text == result2.text  # Identical
```

## JSON Schema Validation

OpenAI's Responses API provides native JSON schema validation with strict guarantees.

### Basic Schema

```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
        "skills": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["name", "age"],
    "additionalProperties": False
}

response = await client.generate(
    messages="Extract: John Doe is a 30-year-old Python developer",
    model="gpt-4.1-mini",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "person_info",
            "schema": schema,
            "strict": True
        }
    }
)

# Response is guaranteed to match schema
import json
data = json.loads(response.text)
```

### Streaming with Schemas

```python
response = await client.stream_with_usage(
    messages="Extract information about Albert Einstein",
    model="gpt-4.1-mini",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "person",
            "schema": schema,
            "strict": True
        }
    }
)

# Parse complete JSON after streaming
data = json.loads(response.text)
```

### Schema Requirements

For strict validation, schemas must:
- Set `"additionalProperties": False` on all objects
- Use only supported JSON Schema features
- Define all required fields explicitly

## Supported Models

Models that support Responses API with JSON schemas:
- gpt-4.1-mini
- gpt-4.1
- gpt-4o-mini
- gpt-4o
- gpt-5-mini
- gpt-5
- gpt-5-nano
- o4-mini (with temperature forced to 1.0)

Check model capabilities:

```python
from steer_llm_sdk.core.capabilities import get_capabilities_for_model

caps = get_capabilities_for_model("gpt-5-mini")
if caps.supports_json_schema:
    print("Model supports Responses API")
if caps.supports_seed:
    print("Model supports seed parameter")

# Temperature handling
if caps.requires_temperature_one:
    print("Model requires temperature=1.0")
elif not caps.supports_temperature:
    print("Model does not support temperature parameter")
```

## Enum Types for Categories

Use enums to restrict outputs to specific values:

```python
schema = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["positive", "negative", "neutral"]
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
    },
    "required": ["category", "confidence"],
    "additionalProperties": False
}

response = await client.generate(
    messages="Analyze sentiment: 'This product is great!'",
    model="gpt-4o-mini",
    temperature=0,
    json_schema=schema
)
```

## Complex Nested Schemas

```python
analysis_schema = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "word_count": {"type": "integer"},
                "sentiment": {
                    "type": "string",
                    "enum": ["positive", "negative", "neutral"]
                }
            },
            "required": ["title", "word_count", "sentiment"],
            "additionalProperties": False
        },
        "key_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "importance": {
                        "type": "string",
                        "enum": ["low", "medium", "high"]
                    }
                },
                "required": ["point", "importance"],
                "additionalProperties": False
            }
        }
    },
    "required": ["summary", "key_points"],
    "additionalProperties": False
}

response = await client.generate(
    messages="Analyze this article: [...]",
    model="gpt-5",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "article_analysis",
            "schema": analysis_schema,
            "strict": True
        }
    }
)
```

## Error Handling

```python
try:
    response = await client.generate(
        messages="Extract data",
        model="gpt-4.1-mini",
        response_format={"type": "json_schema", "json_schema": {...}}
    )
except ValidationError as e:
    print(f"Schema validation failed: {e}")
except ProviderError as e:
    print(f"Provider error: {e}")
```

## Best Practices

1. **Temperature & Seeds**: Use `temperature=0` with `seed` for maximum consistency
2. **JSON Schemas**: Use for structured data extraction and validation
3. **Simple Schemas**: Keep schemas focused and not overly complex
4. **Enum Types**: Use for categorical fields with fixed options
5. **Constraints**: Set appropriate min/max/length constraints
6. **Strict Mode**: Always use `strict: True` for guaranteed validation
7. **Test Schemas**: Validate your schemas with sample data before production
8. **Check Capabilities**: Verify model supports required features

## Model-Specific Notes

- Some variability may still occur due to model updates
- o4-mini requires `temperature=1.0` when using Responses API
- gpt-5-mini omits temperature parameter in Responses API
- Use capability checks instead of hardcoding model names
