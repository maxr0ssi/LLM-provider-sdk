# Cost Calculation Integration Guide for External Repositories

## Overview

The Steer LLM SDK provides a comprehensive cost calculation system that external repositories can easily integrate to track LLM usage costs across multiple providers (OpenAI, Anthropic, xAI). The system supports both **estimated costs** (using combined pricing) and **exact costs** (using separate input/output token pricing).

## Key Integration Points

### 1. Exact Cost Calculation (Recommended)

```python
from steer_llm_sdk.LLMConstants import (
    GPT4O_MINI_INPUT_COST_PER_1K,
    GPT4O_MINI_OUTPUT_COST_PER_1K,
    GPT41_NANO_INPUT_COST_PER_1K,
    GPT41_NANO_OUTPUT_COST_PER_1K
)

def calculate_exact_cost(usage: dict, model_id: str) -> float:
    """Calculate exact cost using separate input/output pricing."""
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    
    if model_id == "gpt-4o-mini":
        input_cost = (prompt_tokens / 1000) * GPT4O_MINI_INPUT_COST_PER_1K
        output_cost = (completion_tokens / 1000) * GPT4O_MINI_OUTPUT_COST_PER_1K
        return input_cost + output_cost
    
    elif model_id == "gpt-4.1-nano":
        input_cost = (prompt_tokens / 1000) * GPT41_NANO_INPUT_COST_PER_1K
        output_cost = (completion_tokens / 1000) * GPT41_NANO_OUTPUT_COST_PER_1K
        return input_cost + output_cost
    
    # Fallback to estimated cost for other models
    return calculate_estimated_cost(usage, model_id)

# Example usage
usage = {
    "prompt_tokens": 500,     # Input tokens
    "completion_tokens": 150, # Output tokens
    "total_tokens": 650
}

exact_cost = calculate_exact_cost(usage, "gpt-4o-mini")
print(f"Exact conversation cost: ${exact_cost:.6f}")
# Output: Exact conversation cost: $0.000165 
# (500 * 0.00015 + 150 * 0.00060 = $0.075 + $0.090 = $0.165)
```

### 2. Estimated Cost Calculation (Current Implementation)

```python
from steer_llm_sdk.llm.registry import calculate_cost, get_config

# Get model configuration with pricing
config = get_config("gpt-4o-mini")

# Calculate estimated cost using combined average pricing
usage = {
    "prompt_tokens": 500,
    "completion_tokens": 150,
    "total_tokens": 650
}

estimated_cost = calculate_cost(usage, config)  # Returns estimated cost in USD
print(f"Estimated conversation cost: ${estimated_cost:.6f}")
# Output: Estimated conversation cost: $0.000244
# (650 * 0.000375 = $0.244) - Less accurate due to averaging
```

### 3. Using the Router with Automatic Cost Calculation

```python
from steer_llm_sdk.llm.router import SteerLLMRouter

router = SteerLLMRouter()
response = await router.generate("gpt-4o-mini", messages)

# Cost automatically calculated and included (currently uses estimated cost)
if response.cost_usd:
    print(f"This conversation cost: ${response.cost_usd:.6f}")

# For exact cost calculation, use the response usage data
if response.usage:
    exact_cost = calculate_exact_cost(response.usage, "gpt-4o-mini")
    print(f"Exact conversation cost: ${exact_cost:.6f}")
```

### 4. Cache Cost Savings Calculation

```python
def calculate_cache_savings(usage: dict, model_id: str) -> float:
    """Calculate exact cost savings from cache usage."""
    cache_info = usage.get("cache_info", {})
    
    # OpenAI cache savings
    if "cached_tokens" in cache_info:
        cached_tokens = cache_info["cached_tokens"]
        if model_id == "gpt-4o-mini":
            return (cached_tokens / 1000) * GPT4O_MINI_INPUT_COST_PER_1K
        elif model_id == "gpt-4.1-nano":
            return (cached_tokens / 1000) * GPT41_NANO_INPUT_COST_PER_1K
    
    # Anthropic cache savings
    if "cache_read_tokens" in cache_info:
        cache_read_tokens = cache_info["cache_read_tokens"]
        # Anthropic input cost (estimated at $0.003 per 1K tokens)
        return (cache_read_tokens / 1000) * 0.003
    
    return 0.0

# Example usage
usage_with_cache = {
    "prompt_tokens": 500,
    "completion_tokens": 150,
    "cache_info": {"cached_tokens": 200}  # 200 tokens from cache
}

base_cost = calculate_exact_cost(usage_with_cache, "gpt-4o-mini")
cache_savings = calculate_cache_savings(usage_with_cache, "gpt-4o-mini")
effective_cost = base_cost - cache_savings

print(f"Base cost: ${base_cost:.6f}")
print(f"Cache savings: ${cache_savings:.6f}")
print(f"Effective cost: ${effective_cost:.6f}")
```

### 5. Budget Management Integration

```python
from steer_llm_sdk.LLMConstants import (
    DEFAULT_LLM_DAILY_BUDGET_USD,
    LLM_COST_WARNING_THRESHOLD,
    MAX_LLM_DAILY_BUDGET_USD
)

# Track user spending against budget
user_daily_cost = 0.35  # Example accumulated cost
budget = DEFAULT_LLM_DAILY_BUDGET_USD  # $0.50

if user_daily_cost >= (budget * LLM_COST_WARNING_THRESHOLD):
    print("Warning: Approaching daily budget limit")

if user_daily_cost >= budget:
    print("Daily budget exceeded")
```

## Implementation Scenarios

### Scenario 1: Chat Application with Exact Cost Tracking

```python
class ChatApp:
    def __init__(self):
        self.router = SteerLLMRouter()
        self.user_costs = {}  # Track per-user costs
    
    async def send_message(self, user_id: str, message: str, model_id: str = "gpt-4o-mini"):
        response = await self.router.generate(model_id, [
            {"role": "user", "content": message}
        ])
        
        # Calculate exact cost instead of estimated
        if response.usage:
            exact_cost = calculate_exact_cost(response.usage, model_id)
            cache_savings = calculate_cache_savings(response.usage, model_id)
            effective_cost = exact_cost - cache_savings
            
            # Track exact cost per user
            self.user_costs[user_id] = self.user_costs.get(user_id, 0) + effective_cost
            
            print(f"Message cost: ${exact_cost:.6f} (saved ${cache_savings:.6f} from cache)")
            print(f"User {user_id} total cost: ${self.user_costs[user_id]:.6f}")
            
        return response.content
```

### Scenario 2: Analytics Dashboard

```python
class LLMAnalytics:
    def __init__(self):
        self.total_cost = 0
        self.conversation_costs = []
    
    def log_conversation_cost(self, usage: dict, model_id: str):
        config = get_config(model_id)
        cost = calculate_cost(usage, config)
        
        if cost:
            self.total_cost += cost
            self.conversation_costs.append({
                "timestamp": datetime.now(),
                "model": model_id,
                "cost": cost,
                "tokens": usage.get("total_tokens", 0)
            })
    
    def get_cost_summary(self):
        return {
            "total_cost": self.total_cost,
            "average_per_conversation": sum(c["cost"] for c in self.conversation_costs) / len(self.conversation_costs),
            "most_expensive_model": max(self.conversation_costs, key=lambda x: x["cost"])["model"]
        }
```

### Scenario 3: Multi-Model Cost Comparison

```python
from steer_llm_sdk.config.models import get_available_models

class ModelCostComparison:
    def compare_models_for_task(self, estimated_tokens: int):
        models = get_available_models()
        costs = {}
        
        for model_id, config in models.items():
            if config.cost_per_1k_tokens:
                estimated_cost = (estimated_tokens / 1000) * config.cost_per_1k_tokens
                costs[model_id] = estimated_cost
        
        # Sort by cost
        return sorted(costs.items(), key=lambda x: x[1])
```

## Available Models and Pricing

### Exact Input/Output Pricing (Recommended)

| Model | Input Cost per 1K tokens | Output Cost per 1K tokens | Combined Estimate |
|-------|---------------------------|----------------------------|-------------------|
| GPT-4.1 Nano | $0.0001 | $0.0004 | $0.00025 |
| GPT-4o Mini | $0.00015 | $0.00060 | $0.000375 |
| Grok 3 Mini | Combined: $0.0004 | Combined: $0.0004 | $0.0004 |
| Claude 3 Haiku | Combined: $0.0025 | Combined: $0.0025 | $0.0025 |

### Cost Comparison Example
For a typical conversation (500 input + 150 output tokens):

| Model | Exact Cost | Estimated Cost | Accuracy |
|-------|------------|----------------|----------|
| GPT-4.1 Nano | $0.000110 | $0.000163 | 48% overestimate |
| GPT-4o Mini | $0.000165 | $0.000244 | 48% overestimate |

**Key Insight**: Output tokens cost 4x more than input tokens, making exact calculation significantly more accurate for cost tracking.

## Advanced Features

### Cache Cost Optimization

The package automatically tracks cache hits and reports savings:

```python
# Cache savings are automatically calculated and logged
response = await router.generate("gpt-4o-mini", messages, use_cache=True)
# Logs: "💰 Cost savings: ~0.000450 USD saved" when cache hits
```

### Budget Controls

```python
# Built-in budget constants for safety
MAX_CONCURRENT_USERS = 20
SYSTEM_DAILY_BUDGET = 10.00  # USD
DEFAULT_DAILY_BUDGET_PER_USER = 0.50  # USD
```

## Integration Best Practices

1. **Initialize once**: Create router instance at application startup
2. **Track per-user**: Implement user-specific cost tracking for multi-user apps
3. **Set budgets**: Use the built-in budget constants as defaults
4. **Monitor cache**: Enable cache optimization to reduce costs
5. **Log costs**: Store cost data for analytics and billing

## Error Handling

```python
try:
    response = await router.generate(model_id, messages)
    if response.cost_usd is None:
        logger.warning(f"Cost calculation unavailable for {model_id}")
except Exception as e:
    logger.error(f"Generation failed: {e}")
```

## Dependencies

To use cost calculation features, install the package:

```bash
pip install steer-llm-sdk
```

The cost calculation system works out-of-the-box with no additional configuration required.