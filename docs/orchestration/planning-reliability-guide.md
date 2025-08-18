# Planning and Reliability Guide

This guide covers the planning and reliability features in the orchestration system: automatic tool selection, retry logic, circuit breakers, and idempotency.

## Overview

The enhanced orchestrator provides production-grade reliability features:
- **Planning**: Automatic tool selection based on request attributes
- **Retry Logic**: Exponential backoff with configurable policies
- **Circuit Breakers**: Provider-level protection against cascading failures
- **Idempotency**: Request deduplication with conflict detection
- **Trace Propagation**: Request and trace ID flow through the system

## Using the Enhanced Orchestrator

### Basic Usage

```python
from steer_llm_sdk.orchestration import ReliableOrchestrator
from steer_llm_sdk.orchestration import OrchestrationConfig

# Create enhanced orchestrator with default configuration
orchestrator = ReliableOrchestrator()

# Let the planner select the appropriate tool
result = await orchestrator.run(
    request={
        "type": "analysis",
        "query": "Analyze the market trends"
    },
    options=OrchestrationConfig(
        idempotency_key="analysis-123",
        trace_id="trace-456"
    )
)
```

### Manual Tool Selection

You can still specify a tool manually, bypassing the planner:

```python
# Explicitly specify the tool
result = await orchestrator.run(
    request="Analyze this data",
    tool_name="analysis_bundle",
    tool_options={"k": 5, "epsilon": 0.1}
)
```

## Planning Configuration

### Rule-Based Planning

The default planner uses rules to select tools:

```python
from steer_llm_sdk.orchestration.planning import (
    RuleBasedPlanner,
    create_type_based_rule,
    create_keyword_based_rule,
    create_budget_aware_rule
)

# Create custom planning rules
planner = RuleBasedPlanner([
    # High priority: Keywords trigger specific tools
    create_keyword_based_rule(
        keywords=["deep", "comprehensive", "thorough"],
        attribute="query",
        tool_name="deep_analysis_tool",
        priority=20
    ),
    
    # Medium priority: Type-based selection
    create_type_based_rule(
        request_type="validation",
        tool_name="validation_tool",
        priority=10
    ),
    
    # Low priority: Budget-aware selection
    create_budget_aware_rule(
        tool_name="analysis_tool",
        low_budget_k=2,
        high_budget_k=5,
        priority=5
    )
])

orchestrator = ReliableOrchestrator(planner=planner)
```

### Custom Planning Rules

Create sophisticated rules with multiple conditions:

```python
from steer_llm_sdk.orchestration.planning import (
    PlanningRule,
    RuleCondition,
    RuleAction
)

# Rule for high-quality analysis requests
high_quality_rule = PlanningRule(
    name="high_quality_analysis",
    priority=30,
    conditions=[
        RuleCondition("type", "equals", "analysis"),
        RuleCondition("metadata.quality", "equals", "high"),
        RuleCondition("metadata.budget", "gt", 0.20)
    ],
    action=RuleAction(
        tool_name="premium_analysis_tool",
        tool_options={"k": 7, "epsilon": 0.05},
        fallback_tools=["standard_analysis_tool", "quick_analysis_tool"]
    )
)

planner.add_rule(high_quality_rule)
```

### Planning Context

The planner considers context when selecting tools:

```python
from steer_llm_sdk.orchestration.planning import PlanRequest

# Provide context for planning decisions
context = PlanRequest(
    budget={"tokens": 5000, "cost_usd": 0.50},
    quality_requirements={"min_confidence": 0.9},
    circuit_breaker_states={
        "expensive_tool": "open",  # Tool is circuit-broken
        "backup_tool": "closed"
    },
    previous_failures=["expensive_tool"]
)

# Planner will avoid circuit-broken tools
result = await orchestrator.run(
    request="Analyze this",
    options=OrchestrationConfig(
        quality_requirements={"min_confidence": 0.9}
    )
)
```

## Reliability Configuration

### Retry Policies

Configure retry behavior for different error types:

```python
from steer_llm_sdk.orchestration.reliability import (
    OrchestratorReliabilityConfig,
    RetryPolicy
)

# Custom retry configuration
reliability_config = OrchestratorReliabilityConfig(
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        jitter_factor=0.1,
        # Selective retry by error type
        retry_on_timeout=True,
        retry_on_rate_limit=True,
        retry_on_server_error=True,
        retry_on_network_error=True,
        # Respect provider retry hints
        respect_retry_after=True,
        max_total_delay=300.0  # 5 minutes max
    )
)

orchestrator = ReliableOrchestrator(
    reliability_config=reliability_config
)
```

### Circuit Breaker Configuration

Configure circuit breakers per provider:

```python
from steer_llm_sdk.reliability import CircuitBreakerConfig

reliability_config = OrchestratorReliabilityConfig(
    circuit_breaker_configs={
        "openai": CircuitBreakerConfig(
            failure_threshold=5,     # Open after 5 failures
            timeout=60.0,           # Stay open for 60 seconds
            window_size=300.0,      # Track failures over 5 minutes
            success_threshold=2     # Need 2 successes to close
        ),
        "anthropic": CircuitBreakerConfig(
            failure_threshold=3,
            timeout=120.0,
            window_size=300.0,
            success_threshold=1
        )
    },
    # Fallback configuration
    enable_fallback=True,
    max_fallback_attempts=2
)
```

### Tool Provider Mapping

Tools can specify their provider for circuit breaker association:

```python
class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def provider(self) -> str:
        return "openai"  # Associates with OpenAI circuit breaker
    
    async def execute(self, request, options=None, event_manager=None):
        # Tool implementation
        result = await call_openai_api(...)
        
        # Include provider in response for dynamic mapping
        return {
            "data": result,
            "provider": "openai"
        }
```

## Idempotency

### Basic Idempotency

Prevent duplicate processing of requests:

```python
# First request
result1 = await orchestrator.run(
    request="Process payment for order 123",
    tool_name="payment_processor",
    options=OrchestrationConfig(
        idempotency_key="payment-order-123"
    )
)

# Duplicate request returns cached result
result2 = await orchestrator.run(
    request="Process payment for order 123",
    tool_name="payment_processor",
    options=OrchestrationConfig(
        idempotency_key="payment-order-123"
    )
)

assert result1 == result2  # Same result, no duplicate processing
```

### Conflict Detection

The system detects when the same idempotency key is used with different requests:

```python
# First request
await orchestrator.run(
    request="Process payment for $100",
    options=OrchestrationConfig(
        idempotency_key="payment-123"
    )
)

# Different request with same key raises ConflictError
try:
    await orchestrator.run(
        request="Process payment for $200",  # Different amount!
        options=OrchestrationConfig(
            idempotency_key="payment-123"
        )
    )
except ConflictError as e:
    print(f"Conflict detected: {e}")
```

### Custom Idempotency Storage

Use persistent storage for production:

```python
from steer_llm_sdk.reliability.idempotency import IdempotencyManager

# Custom storage backend (e.g., Redis, DynamoDB)
class RedisIdempotencyManager(IdempotencyManager):
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 900  # 15 minutes
    
    async def get(self, key: str) -> Optional[Any]:
        value = await self.redis.get(f"idempotency:{key}")
        return json.loads(value) if value else None
    
    async def store(self, key: str, value: Any) -> None:
        await self.redis.setex(
            f"idempotency:{key}",
            self.ttl,
            json.dumps(value)
        )

# Use custom manager
orchestrator = ReliableOrchestrator(
    idempotency_manager=RedisIdempotencyManager(redis_client)
)
```

## Trace and Request ID Propagation

### Automatic ID Generation

IDs are automatically generated if not provided:

```python
# No IDs provided - automatically generated
result = await orchestrator.run("Test request")

print(result.metadata["request_id"])  # e.g., "a1b2c3d4-..."
print(result.metadata["trace_id"])    # Same as request_id
```

### Explicit ID Propagation

Provide IDs for distributed tracing:

```python
# Explicit IDs for tracing
result = await orchestrator.run(
    request="Analyze data",
    options=OrchestrationConfig(
        trace_id="trace-123",      # Distributed trace ID
        request_id="req-456"       # Unique request ID
    )
)

# IDs are propagated to tools
# Tools receive: options["trace_id"] and options["request_id"]
```

## Complete Example

Here's a complete example using all planning and reliability features:

```python
from steer_llm_sdk.orchestration import ReliableOrchestrator
from steer_llm_sdk.orchestration import OrchestrationConfig
from steer_llm_sdk.orchestration.planning import (
    RuleBasedPlanner,
    create_type_based_rule,
    create_keyword_based_rule
)
from steer_llm_sdk.orchestration.reliability import (
    OrchestratorReliabilityConfig,
    RetryPolicy
)

# Configure planning rules
planner = RuleBasedPlanner([
    create_keyword_based_rule(
        ["urgent", "critical"],
        "metadata.priority",
        "fast_tool",
        priority=100
    ),
    create_type_based_rule(
        "analysis",
        "analysis_tool",
        priority=10,
        k=3
    )
])

# Configure reliability
reliability_config = OrchestratorReliabilityConfig(
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_delay=0.5,
        retry_on_rate_limit=True
    ),
    enable_fallback=True
)

# Create orchestrator
orchestrator = ReliableOrchestrator(
    planner=planner,
    reliability_config=reliability_config
)

# Execute with all features
result = await orchestrator.run(
    request={
        "type": "analysis",
        "query": "Analyze customer sentiment",
        "metadata": {
            "priority": "urgent"
        }
    },
    options=OrchestrationConfig(
        idempotency_key="sentiment-analysis-2024-01",
        trace_id="distributed-trace-789",
        request_id="request-abc-123",
        budget={"tokens": 5000, "cost_usd": 0.25},
        quality_requirements={"min_confidence": 0.85}
    )
)

print(f"Selected tool: {result.metadata['tool_name']}")
print(f"Total attempts: {result.metadata.get('retry_attempts', 1)}")
print(f"Confidence: {result.metadata.get('confidence', 'N/A')}")
```

## Best Practices

1. **Planning Rules**
   - Order rules by priority (highest first)
   - Use specific conditions to avoid conflicts
   - Provide fallback tools for critical operations

2. **Retry Configuration**
   - Set reasonable retry limits (2-3 attempts)
   - Use exponential backoff to avoid overwhelming providers
   - Respect provider retry-after headers

3. **Circuit Breakers**
   - Configure per-provider, not per-tool
   - Set failure thresholds based on provider SLAs
   - Monitor circuit breaker state changes

4. **Idempotency**
   - Use meaningful, deterministic keys
   - Include operation type in the key
   - Set appropriate TTLs for your use case

5. **Tracing**
   - Always propagate trace IDs in distributed systems
   - Use request IDs for debugging
   - Log IDs with all operations

## Monitoring and Debugging

### Circuit Breaker State

Check circuit breaker states:

```python
# Get current states for monitoring
states = orchestrator._get_circuit_breaker_states()
for key, state in states.items():
    print(f"{key}: {state}")
    
# Example output:
# openai:analysis_tool: closed
# anthropic:backup_tool: open
```

### Retry Metrics

The retry manager tracks metrics:

```python
# Access retry metrics (if using custom metrics sink)
metrics = orchestrator.reliable_executor.retry_manager.metrics
print(f"Total retry attempts: {metrics.retry_attempts}")
print(f"Retry success rate: {metrics.retry_successes / metrics.retry_attempts}")
```

### Event Streaming

Monitor tool execution with streaming events:

```python
from steer_llm_sdk.streaming.manager import EventManager

async def on_delta(event):
    if event.metadata.get("event_type") == "retry_attempt":
        print(f"Retry attempt {event.metadata['attempt']} for {event.metadata['source']}")

event_manager = EventManager(on_delta=on_delta)

result = await orchestrator.run(
    request="Test",
    options=OrchestrationConfig(streaming=True),
    event_manager=event_manager
)
```

## Migration from Base Orchestrator

To migrate from the base orchestrator to the enhanced version:

1. **Import Change**:
   ```python
   # Old
   from steer_llm_sdk.orchestration import Orchestrator
   
   # New
   from steer_llm_sdk.orchestration import ReliableOrchestrator
   ```

2. **Tool Selection**:
   - The `tool_name` parameter is now optional
   - If not provided, the planner selects the tool
   - Existing code with explicit tool names still works

3. **New Options**:
   - Add `idempotency_key` for deduplication
   - Add `quality_requirements` for planning hints
   - Circuit breakers are enabled by default

4. **Backward Compatibility**:
   - All existing functionality remains
   - New features are opt-in
   - Default configuration provides sensible behavior