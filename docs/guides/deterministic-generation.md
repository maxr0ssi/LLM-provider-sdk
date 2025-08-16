# Deterministic Generation Guide

This guide explains how to achieve consistent, reproducible outputs from LLMs using the Steer LLM SDK.

## Understanding Determinism in LLMs

LLMs are inherently probabilistic, but you can make their outputs more deterministic through:
- Temperature control
- Seed parameters
- Top-p/top-k settings
- Model selection
- Response format constraints

## Basic Deterministic Settings

### Temperature Control

```python
from steer_llm_sdk import SteerLLMClient

client = SteerLLMClient()

# Temperature = 0 for most deterministic output
response = await client.generate(
    messages="Define artificial intelligence in exactly one sentence.",
    model="gpt-4",
    temperature=0.0,  # No randomness
    max_tokens=50
)

# Multiple runs should produce identical output
response1 = await client.generate(messages="What is 2+2?", model="gpt-4", temperature=0)
response2 = await client.generate(messages="What is 2+2?", model="gpt-4", temperature=0)
assert response1 == response2  # Should be identical
```

### Using Seeds

Some models support seed parameters for reproducibility:

```python
# GPT-4 and GPT-5 models support seeds
async def generate_with_seed(prompt: str, seed: int = 42):
    return await client.generate(
        messages=prompt,
        model="gpt-5-mini",
        temperature=0,
        seed=seed,  # Fixed seed for reproducibility
        max_tokens=100
    )

# Same seed = same output
result1 = await generate_with_seed("Write a haiku about coding")
result2 = await generate_with_seed("Write a haiku about coding")
assert result1 == result2

# Different seed = different output (even with temperature=0)
result3 = await generate_with_seed("Write a haiku about coding", seed=123)
assert result1 != result3
```

## Advanced Deterministic Patterns

### Structured Output for Consistency

```python
# Use JSON schemas to enforce structure
classification_schema = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["positive", "negative", "neutral"]  # Fixed options
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3  # Limit variability
        }
    },
    "required": ["category", "confidence"],
    "additionalProperties": False
}

async def classify_deterministic(text: str):
    return await client.generate(
        messages=f"Classify this text: {text}",
        model="gpt-4.1-mini",
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "classification",
                "schema": classification_schema,
                "strict": True
            }
        }
    )
```

### Constrained Generation

```python
# Use specific prompting techniques for consistency
async def generate_constrained(data: dict):
    prompt = f"""
You must follow these rules EXACTLY:
1. Output must be exactly 3 bullet points
2. Each bullet point must start with a number
3. Each bullet point must be exactly one sentence
4. Use only facts from the provided data
5. Do not add any interpretation or additional information

Data: {data}

Output:"""
    
    return await client.generate(
        messages=prompt,
        model="gpt-4",
        temperature=0,
        max_tokens=150,
        stop=["\n4."]  # Stop after 3 points
    )
```

## Model-Specific Determinism

### OpenAI Models

```python
# GPT-4 and GPT-3.5 determinism
async def openai_deterministic(prompt: str):
    return await client.generate(
        messages=prompt,
        model="gpt-4",
        temperature=0,
        top_p=1.0,      # No nucleus sampling
        presence_penalty=0,  # No penalty
        frequency_penalty=0,  # No penalty
        seed=12345      # Supported in newer versions
    )
```

### Anthropic Models

```python
# Claude models determinism
async def claude_deterministic(prompt: str):
    return await client.generate(
        messages=prompt,
        model="claude-3-opus",
        temperature=0,
        top_p=1.0,
        # Claude doesn't support seeds yet
        # Use explicit instructions instead
        max_tokens=100
    )
```

### Model Capability Checking

```python
from steer_llm_sdk.core.routing import get_config

def supports_deterministic_generation(model: str) -> dict:
    """Check model's deterministic capabilities."""
    config = get_config(model)
    
    return {
        "supports_zero_temperature": not config.fixed_temperature,
        "supports_seed": config.supports_seed,
        "temperature_range": (config.min_temperature, config.max_temperature),
        "has_json_mode": config.supports_json_schema
    }

# Check before using
model = "gpt-5-mini"
capabilities = supports_deterministic_generation(model)

if capabilities["supports_seed"]:
    # Use seed for reproducibility
    response = await client.generate(
        messages="Test",
        model=model,
        temperature=0,
        seed=42
    )
else:
    # Rely on temperature=0 only
    response = await client.generate(
        messages="Test",
        model=model,
        temperature=0
    )
```

## Testing Deterministic Behavior

### Reproducibility Tests

```python
import hashlib
import json

async def test_reproducibility(prompt: str, model: str, runs: int = 5):
    """Test if outputs are reproducible."""
    
    settings = {
        "temperature": 0,
        "seed": 42,
        "max_tokens": 100
    }
    
    outputs = []
    hashes = []
    
    for i in range(runs):
        response = await client.generate(
            messages=prompt,
            model=model,
            **settings
        )
        
        outputs.append(response)
        # Hash for easy comparison
        hashes.append(hashlib.md5(response.encode()).hexdigest())
    
    # Check if all outputs are identical
    unique_outputs = len(set(hashes))
    
    print(f"Model: {model}")
    print(f"Runs: {runs}")
    print(f"Unique outputs: {unique_outputs}")
    print(f"Deterministic: {unique_outputs == 1}")
    
    if unique_outputs > 1:
        print("Different outputs detected:")
        for i, output in enumerate(outputs):
            print(f"Run {i+1}: {output[:50]}...")
    
    return unique_outputs == 1

# Test different models
for model in ["gpt-4", "claude-3-opus", "gpt-3.5-turbo"]:
    is_deterministic = await test_reproducibility(
        "What is the capital of France?",
        model
    )
```

### Determinism Metrics

```python
class DeterminismAnalyzer:
    """Analyze determinism of model outputs."""
    
    def __init__(self):
        self.results = {}
    
    async def analyze_model(self, model: str, test_prompts: list, runs_per_prompt: int = 10):
        """Analyze determinism for a model."""
        
        model_results = {
            "prompts_tested": len(test_prompts),
            "total_runs": len(test_prompts) * runs_per_prompt,
            "deterministic_prompts": 0,
            "variability_scores": []
        }
        
        for prompt in test_prompts:
            outputs = []
            
            # Run multiple times
            for _ in range(runs_per_prompt):
                response = await client.generate(
                    messages=prompt,
                    model=model,
                    temperature=0,
                    seed=42 if "gpt" in model else None
                )
                outputs.append(response)
            
            # Calculate variability
            unique_outputs = len(set(outputs))
            variability = (unique_outputs - 1) / (runs_per_prompt - 1) if runs_per_prompt > 1 else 0
            
            model_results["variability_scores"].append(variability)
            if unique_outputs == 1:
                model_results["deterministic_prompts"] += 1
        
        # Calculate overall metrics
        model_results["determinism_rate"] = model_results["deterministic_prompts"] / len(test_prompts)
        model_results["avg_variability"] = sum(model_results["variability_scores"]) / len(test_prompts)
        
        self.results[model] = model_results
        return model_results
    
    def print_report(self):
        """Print determinism analysis report."""
        print("Determinism Analysis Report")
        print("=" * 50)
        
        for model, results in self.results.items():
            print(f"\nModel: {model}")
            print(f"  Determinism Rate: {results['determinism_rate']:.2%}")
            print(f"  Average Variability: {results['avg_variability']:.4f}")
            print(f"  Deterministic Prompts: {results['deterministic_prompts']}/{results['prompts_tested']}")

# Run analysis
analyzer = DeterminismAnalyzer()

test_prompts = [
    "What is 2+2?",
    "Define gravity in one sentence.",
    "List the primary colors.",
    "Write a haiku about mountains.",
    "Translate 'hello' to Spanish."
]

for model in ["gpt-4", "claude-3-opus"]:
    await analyzer.analyze_model(model, test_prompts)

analyzer.print_report()
```

## Use Cases for Deterministic Generation

### 1. Automated Testing

```python
async def test_extraction_function():
    """Test that extraction produces consistent results."""
    
    test_text = "John Doe, age 30, lives in New York."
    
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "city": {"type": "string"}
        },
        "required": ["name", "age", "city"],
        "additionalProperties": False
    }
    
    # Should always extract the same data
    result = await client.generate(
        messages=f"Extract person information from: {test_text}",
        model="gpt-4",
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "person", "schema": schema}
        }
    )
    
    expected = {"name": "John Doe", "age": 30, "city": "New York"}
    assert json.loads(result) == expected
```

### 2. Data Processing Pipelines

```python
class DeterministicProcessor:
    """Process data with deterministic transformations."""
    
    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self.client = SteerLLMClient()
    
    async def normalize_address(self, address: str) -> dict:
        """Normalize address to standard format."""
        
        schema = {
            "type": "object",
            "properties": {
                "street": {"type": "string"},
                "city": {"type": "string"},
                "state": {"type": "string"},
                "zip": {"type": "string"},
                "country": {"type": "string"}
            },
            "additionalProperties": False
        }
        
        response = await self.client.generate(
            messages=f"Parse this address into components: {address}",
            model=self.model,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "address", "schema": schema}
            }
        )
        
        return json.loads(response)
    
    async def classify_document(self, text: str) -> str:
        """Classify document type deterministically."""
        
        response = await self.client.generate(
            messages=f"""Classify this document into EXACTLY ONE of these categories:
            - invoice
            - receipt  
            - contract
            - letter
            - report
            
            Document: {text[:500]}
            
            Category:""",
            model=self.model,
            temperature=0,
            max_tokens=10
        )
        
        return response.strip().lower()
```

### 3. Content Moderation

```python
async def moderate_content_deterministic(text: str) -> dict:
    """Deterministic content moderation."""
    
    moderation_schema = {
        "type": "object",
        "properties": {
            "safe": {"type": "boolean"},
            "categories": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["violence", "harassment", "hate", "self-harm", "sexual", "none"]
                }
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "none"]
            }
        },
        "required": ["safe", "categories", "severity"],
        "additionalProperties": False
    }
    
    return await client.generate(
        messages=f"Analyze this content for safety issues: {text}",
        model="gpt-4",
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "moderation",
                "schema": moderation_schema
            }
        }
    )
```

## Handling Non-Deterministic Cases

### Ensemble Approach

```python
async def ensemble_generation(prompt: str, models: list, runs: int = 3):
    """Use multiple models/runs and pick consensus."""
    
    all_outputs = []
    
    for model in models:
        for _ in range(runs):
            output = await client.generate(
                messages=prompt,
                model=model,
                temperature=0
            )
            all_outputs.append(output)
    
    # Find most common output
    from collections import Counter
    output_counts = Counter(all_outputs)
    consensus = output_counts.most_common(1)[0]
    
    return {
        "consensus_output": consensus[0],
        "confidence": consensus[1] / len(all_outputs),
        "all_outputs": output_counts
    }
```

### Validation and Retry

```python
async def generate_with_validation(prompt: str, validator, max_retries: int = 3):
    """Generate with validation and retry."""
    
    for attempt in range(max_retries):
        response = await client.generate(
            messages=prompt,
            model="gpt-4",
            temperature=0,
            seed=42 + attempt  # Different seed per retry
        )
        
        if validator(response):
            return response, attempt + 1
    
    raise ValueError(f"Failed to generate valid output after {max_retries} attempts")

# Example validator
def validate_email(text: str) -> bool:
    import re
    return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', text.strip()))

# Use with validation
email, attempts = await generate_with_validation(
    "Generate a professional email address for John Smith at Acme Corp",
    validate_email
)
```

## Best Practices

1. **Always use temperature=0** for maximum determinism
2. **Use seeds when available** - Check model capabilities first
3. **Constrain outputs** with JSON schemas or explicit formatting
4. **Test reproducibility** in your specific use case
5. **Document non-deterministic behavior** when it occurs
6. **Use structured prompts** with clear, unambiguous instructions
7. **Implement validation** for critical applications
8. **Consider model selection** - Some models are more deterministic
9. **Cache deterministic outputs** to ensure consistency
10. **Monitor for drift** - Models can change over time

## Limitations

- True determinism is not guaranteed across:
  - Model updates
  - API infrastructure changes  
  - Different API endpoints or regions
- Some models don't support seeds
- Complex creative tasks are inherently less deterministic
- Floating-point operations can introduce minor variations