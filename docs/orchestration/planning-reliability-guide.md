# Planning and Reliability Guide

Guide to automatic tool selection, retry logic, circuit breakers, and idempotency in the orchestration system.

## ReliableOrchestrator

```python
from steer_llm_sdk.orchestration import ReliableOrchestrator, OrchestrationConfig

orchestrator = ReliableOrchestrator()

# Automatic tool selection
result = await orchestrator.run(
    request={"type": "analysis", "query": "Analyze the market trends"},
    options=OrchestrationConfig(
        idempotency_key="analysis-123",
        trace_id="trace-456"
    )
)

# Manual tool selection
result = await orchestrator.run(
    request="Analyze this data",
    tool_name="analysis_bundle",
    tool_options={"k": 5, "epsilon": 0.1}
)
```

## Planning Configuration

### Rule-Based Planning

```python
from steer_llm_sdk.orchestration.planning import (
    RuleBasedPlanner,
    create_type_based_rule,
    create_keyword_based_rule
)

planner = RuleBasedPlanner([
    create_keyword_based_rule(
        keywords=["deep", "comprehensive"],
        attribute="query",
        tool_name="deep_analysis_tool",
        priority=20
    ),
    create_type_based_rule(
        request_type="validation",
        tool_name="validation_tool",
        priority=10
    )
])

orchestrator = ReliableOrchestrator(planner=planner)
```

### Custom Rules

```python
from steer_llm_sdk.orchestration.planning import PlanningRule, RuleCondition, RuleAction

rule = PlanningRule(
    name="high_quality_analysis",
    priority=30,
    conditions=[
        RuleCondition("type", "equals", "analysis"),
        RuleCondition("metadata.quality", "equals", "high")
    ],
    action=RuleAction(
        tool_name="premium_analysis_tool",
        tool_options={"k": 7}
    )
)
```

## Retry Configuration

```python
from steer_llm_sdk.orchestration.reliability import ReliabilityConfig, RetryPolicy

reliability_config = ReliabilityConfig(
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        respect_retry_after=True
    )
)

orchestrator = ReliableOrchestrator(reliability_config=reliability_config)
```

## Circuit Breakers

```python
from steer_llm_sdk.reliability import CircuitBreakerConfig

reliability_config = ReliabilityConfig(
    circuit_breaker_configs={
        "openai": CircuitBreakerConfig(
            failure_threshold=5,
            timeout=60.0,
            window_size=300.0
        ),
        "anthropic": CircuitBreakerConfig(
            failure_threshold=3,
            timeout=120.0
        )
    }
)
```

## Idempotency

```python
# Prevent duplicate execution
result = await orchestrator.run(
    request={"query": "Important analysis"},
    options=OrchestrationConfig(
        idempotency_key="unique-request-123"
    )
)

# Second call with same key returns cached result
result2 = await orchestrator.run(
    request={"query": "Important analysis"},
    options=OrchestrationConfig(
        idempotency_key="unique-request-123"
    )
)
# result2 is returned from cache, no re-execution
```

### Idempotency Configuration

```python
reliability_config = ReliabilityConfig(
    idempotency_enabled=True,
    idempotency_ttl_ms=3600000,  # 1 hour
    conflict_detection=True
)
```

## Trace Propagation

```python
result = await orchestrator.run(
    request={"query": "Analysis request"},
    options=OrchestrationConfig(
        trace_id="trace-abc",
        request_id="req-123"
    )
)

# Trace IDs flow through all operations
print(result.trace_id)  # "trace-abc"
print(result.request_id)  # "req-123"
```

## Error Handling

```python
from steer_llm_sdk.orchestration import (
    OrchestratorError,
    ToolExecutionError,
    BudgetExceeded,
    ConflictError
)

try:
    result = await orchestrator.run(
        request={"query": "Analyze"},
        options=OrchestrationConfig(
            budget={"tokens": 1000, "cost_usd": 0.10}
        )
    )
except BudgetExceeded as e:
    print(f"Budget exceeded: {e.budget_type}")
except ToolExecutionError as e:
    print(f"Tool failed: {e.tool_name}")
except ConflictError as e:
    print(f"Idempotency conflict: {e.key}")
```

## Best Practices

1. Use idempotency keys for critical operations
2. Configure circuit breakers per provider based on SLAs
3. Respect retry-after headers from providers
4. Use trace IDs for distributed request tracking
5. Set appropriate budget limits to prevent runaway costs
6. Let the planner select tools when possible
7. Monitor circuit breaker states and adjust thresholds
