# Advanced Responses API Usage

This guide covers advanced usage patterns for OpenAI's Responses API through the Steer LLM SDK.

## Overview

The Responses API is OpenAI's unified endpoint that provides:
- Native JSON schema validation
- Structured output guarantees
- Streaming with usage data
- Deterministic generation
- Enhanced error handling

## Structured Output with JSON Schema

### Basic JSON Schema

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

# Define a JSON schema
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
        "skills": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["name", "age"],
    "additionalProperties": False
}

# Generate with schema validation
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
data = json.loads(response)
print(f"Name: {data['name']}, Age: {data['age']}")
```

### Complex Nested Schemas

```python
# Complex schema with nested objects
analysis_schema = {
    "type": "object",
    "properties": {
        "document": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string", "maxLength": 200},
                "language": {"type": "string"},
                "metadata": {
                    "type": "object",
                    "properties": {
                        "word_count": {"type": "integer"},
                        "reading_time_minutes": {"type": "number"},
                        "complexity_score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 10
                        }
                    },
                    "required": ["word_count"],
                    "additionalProperties": False
                }
            },
            "required": ["title", "summary", "metadata"],
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
                    },
                    "evidence": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["point", "importance"],
                "additionalProperties": False
            },
            "minItems": 1,
            "maxItems": 5
        },
        "sentiment": {
            "type": "object",
            "properties": {
                "overall": {
                    "type": "string",
                    "enum": ["positive", "negative", "neutral", "mixed"]
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["overall", "confidence"],
            "additionalProperties": False
        }
    },
    "required": ["document", "key_points", "sentiment"],
    "additionalProperties": False
}

response = await client.generate(
    messages=f"Analyze this document: {document_text}",
    model="gpt-5-mini",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "document_analysis",
            "schema": analysis_schema,
            "strict": True
        }
    },
    temperature=0  # For consistency
)
```

### Schema Validation Patterns

```python
from typing import Dict, Any
import jsonschema

def validate_and_generate(prompt: str, schema: Dict[str, Any], model: str = "gpt-4.1-mini"):
    """Generate and validate structured output."""
    
    # First validate the schema itself
    try:
        jsonschema.Draft7Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        raise ValueError(f"Invalid schema: {e}")
    
    # Generate with schema
    response = await client.generate(
        messages=prompt,
        model=model,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "output",
                "schema": schema,
                "strict": True  # Enforce strict validation
            }
        },
        temperature=0,
        seed=42  # For reproducibility
    )
    
    # Parse and validate (SDK handles this, but we can double-check)
    result = json.loads(response)
    jsonschema.validate(result, schema)
    
    return result
```

## Streaming with JSON

### Streaming JSON Objects

```python
from steer_llm_sdk.models.streaming import StreamingOptions

# Configure JSON streaming
streaming_options = StreamingOptions(
    enable_json_stream_handler=True,
    enable_usage_aggregation=True
)

# Track JSON objects as they stream
json_objects = []

async def on_delta(event):
    if event.is_json:
        # This is a complete JSON object
        json_objects.append(json.loads(event.get_text()))

response = await client.stream_with_usage(
    messages="Generate a list of 3 products with name and price",
    model="gpt-4.1-mini",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "product_list",
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "price": {"type": "number"}
                    },
                    "required": ["name", "price"],
                    "additionalProperties": False
                }
            }
        }
    },
    streaming_options=streaming_options,
    on_delta=on_delta
)

# Final validated JSON
final_json = json.loads(response.get_text())
print(f"Streamed {len(json_objects)} objects")
```

### Progressive JSON Parsing

```python
from steer_llm_sdk.streaming.json_handler import JsonStreamHandler

# Manual JSON handler for custom processing
handler = JsonStreamHandler()
partial_objects = []

async def on_delta(event):
    text = event.get_text()
    handler.process_chunk(text)
    
    # Check for complete objects
    if handler.has_complete_object():
        obj = handler.get_final_object()
        partial_objects.append(obj)
        print(f"Complete object found: {obj}")

response = await client.stream_with_usage(
    messages="Generate JSON data",
    model="gpt-5-mini",
    response_format={"type": "json_object"},
    on_delta=on_delta
)
```

## Deterministic Generation

### Using Seeds

```python
# Generate consistent outputs across runs
async def generate_deterministic(prompt: str, seed: int = 42):
    return await client.generate(
        messages=prompt,
        model="gpt-5-mini",
        temperature=0,        # No randomness
        top_p=1.0,           # No nucleus sampling
        seed=seed,           # Fixed seed
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "analysis",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "score": {"type": "number"}
                    },
                    "required": ["summary", "score"],
                    "additionalProperties": False
                }
            }
        }
    )

# Multiple runs produce same output
result1 = await generate_deterministic("Analyze this text: Hello world")
result2 = await generate_deterministic("Analyze this text: Hello world")
assert result1 == result2  # Same output
```

### Deterministic Extraction

```python
from typing import List, Dict

async def extract_entities(text: str, entity_types: List[str]) -> Dict[str, List[str]]:
    """Extract entities deterministically."""
    
    schema = {
        "type": "object",
        "properties": {
            entity_type: {
                "type": "array",
                "items": {"type": "string"},
                "description": f"List of {entity_type} entities found"
            }
            for entity_type in entity_types
        },
        "additionalProperties": False
    }
    
    prompt = f"""
    Extract the following entity types from the text:
    {', '.join(entity_types)}
    
    Text: {text}
    """
    
    response = await client.generate(
        messages=prompt,
        model="gpt-4.1-mini",
        temperature=0,
        seed=12345,  # Fixed seed for consistency
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "entities",
                "schema": schema,
                "strict": True
            }
        }
    )
    
    return json.loads(response)

# Example usage
entities = await extract_entities(
    "Apple Inc. announced a new iPhone in Cupertino, California.",
    ["companies", "products", "locations"]
)
# Result: {
#   "companies": ["Apple Inc."],
#   "products": ["iPhone"],
#   "locations": ["Cupertino", "California"]
# }
```

## Error Handling

### Schema Validation Errors

```python
async def safe_generate_json(prompt: str, schema: Dict[str, Any]):
    """Generate with comprehensive error handling."""
    try:
        response = await client.generate(
            messages=prompt,
            model="gpt-5-mini",
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "output",
                    "schema": schema,
                    "strict": True
                }
            }
        )
        return json.loads(response), None
    
    except json.JSONDecodeError as e:
        # Model output wasn't valid JSON
        return None, f"JSON parse error: {e}"
    
    except Exception as e:
        if "schema validation" in str(e).lower():
            # Schema validation failed
            return None, f"Schema validation error: {e}"
        elif "invalid schema" in str(e).lower():
            # The schema itself is invalid
            return None, f"Invalid schema definition: {e}"
        else:
            # Other errors
            return None, f"Generation error: {e}"

# Usage with error handling
result, error = await safe_generate_json(
    "Extract user info",
    {"type": "object", "properties": {"name": {"type": "string"}}}
)

if error:
    print(f"Failed: {error}")
else:
    print(f"Success: {result}")
```

### Retry with Schema Relaxation

```python
async def generate_with_fallback(prompt: str, strict_schema: Dict[str, Any]):
    """Try strict schema first, fall back to relaxed version."""
    
    # Try with strict validation
    try:
        response = await client.generate(
            messages=prompt,
            model="gpt-5-mini",
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "strict_output",
                    "schema": strict_schema,
                    "strict": True
                }
            }
        )
        return json.loads(response), "strict"
    
    except Exception as e:
        print(f"Strict schema failed: {e}")
        
        # Fall back to relaxed schema
        relaxed_schema = strict_schema.copy()
        relaxed_schema["additionalProperties"] = True  # Allow extra fields
        
        # Remove some requirements
        if "required" in relaxed_schema:
            relaxed_schema["required"] = []
        
        response = await client.generate(
            messages=prompt + "\n\nNote: Output as much as possible even if some fields are unknown.",
            model="gpt-5-mini",
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "relaxed_output",
                    "schema": relaxed_schema,
                    "strict": False
                }
            }
        )
        return json.loads(response), "relaxed"
```

## Performance Optimization

### Batch Processing

```python
from typing import List, Tuple
import asyncio

async def batch_extract(items: List[str], schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process multiple items with the same schema."""
    
    async def process_item(item: str) -> Tuple[str, Dict[str, Any]]:
        response = await client.generate(
            messages=f"Extract information from: {item}",
            model="gpt-4.1-mini",
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction",
                    "schema": schema
                }
            },
            temperature=0
        )
        return item, json.loads(response)
    
    # Process in parallel with concurrency limit
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
    
    async def limited_process(item: str):
        async with semaphore:
            return await process_item(item)
    
    results = await asyncio.gather(*[
        limited_process(item) for item in items
    ])
    
    return [result[1] for result in results]
```

### Schema Caching

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_compiled_schema(schema_json: str):
    """Cache compiled schemas for reuse."""
    schema = json.loads(schema_json)
    # Validate schema once
    jsonschema.Draft7Validator.check_schema(schema)
    return schema

async def generate_with_cached_schema(prompt: str, schema_name: str):
    """Use pre-compiled schemas for better performance."""
    
    # Define schemas once
    schemas = {
        "user_info": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "age": {"type": "integer", "minimum": 0}
            },
            "required": ["name", "email"],
            "additionalProperties": False
        },
        "product_review": {
            "type": "object",
            "properties": {
                "rating": {"type": "integer", "minimum": 1, "maximum": 5},
                "title": {"type": "string", "maxLength": 100},
                "review": {"type": "string"},
                "pros": {"type": "array", "items": {"type": "string"}},
                "cons": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["rating", "review"],
            "additionalProperties": False
        }
    }
    
    schema = schemas.get(schema_name)
    if not schema:
        raise ValueError(f"Unknown schema: {schema_name}")
    
    return await client.generate(
        messages=prompt,
        model="gpt-5-mini",
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": schema
            }
        }
    )
```

## Model-Specific Features

### GPT-4.1 Mini

```python
# Optimized for structured extraction
response = await client.generate(
    messages="Extract product details from this description",
    model="gpt-4.1-mini",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "product",
            "schema": product_schema,
            "strict": True
        }
    },
    max_tokens=256  # Smaller model, limit output
)
```

### GPT-5 Mini

```python
# Enhanced reasoning capabilities
response = await client.generate(
    messages="Analyze and categorize this data",
    model="gpt-5-mini",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "analysis",
            "schema": analysis_schema
        }
    },
    # Note: temperature parameter not supported in Responses API for gpt-5-mini
    # Use seed for consistency instead
    seed=42
)
```

## Integration Examples

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

class ExtractionRequest(BaseModel):
    text: str
    schema_name: str
    model: str = "gpt-4.1-mini"

class ExtractionResponse(BaseModel):
    data: Dict[str, Any]
    model: str
    tokens_used: int

@app.post("/extract", response_model=ExtractionResponse)
async def extract_structured_data(request: ExtractionRequest):
    """Extract structured data using Responses API."""
    
    # Predefined schemas
    schemas = {
        "contact": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"}
            },
            "additionalProperties": False
        }
    }
    
    schema = schemas.get(request.schema_name)
    if not schema:
        raise HTTPException(status_code=400, detail="Unknown schema")
    
    try:
        # Use SDK with metrics
        response = await client.generate(
            messages=f"Extract {request.schema_name} information from: {request.text}",
            model=request.model,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "schema": schema
                }
            }
        )
        
        # Get usage from response
        usage = getattr(response, 'usage', None)
        tokens = usage.total_tokens if usage else 0
        
        return ExtractionResponse(
            data=json.loads(response),
            model=request.model,
            tokens_used=tokens
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Best Practices

1. **Always use `additionalProperties: false`** in schemas for strict validation
2. **Set temperature=0** for consistent outputs
3. **Use seeds** when reproducibility is important
4. **Validate schemas** before sending to API
5. **Handle errors gracefully** with fallback strategies
6. **Cache schemas** for better performance
7. **Use appropriate models** - gpt-4.1-mini for simple extraction, gpt-5-mini for complex reasoning
8. **Monitor token usage** as structured outputs can be token-intensive
9. **Test schemas thoroughly** before production use
10. **Use streaming** for real-time feedback on long generations