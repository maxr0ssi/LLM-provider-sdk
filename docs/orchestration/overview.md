# Orchestration Overview

Tool-based architecture for executing complex LLM operations with reliability features.

## Key Features

- Tool-based architecture with pluggable tools
- Automatic planning and tool selection
- Retry logic, circuit breakers, and idempotency
- Evidence Bundles with statistical analysis
- Streaming support for real-time progress
- Budget management (tokens, cost, time)

## Quick Start

### Register Tools

```python
from steer_llm_sdk import SteerLLMClient
from my_app.tools import FeasibilityBundleTool

client = SteerLLMClient()
client.register_tool(FeasibilityBundleTool())

# List tools
print(client.list_tools())
```

### Execute Tools

```python
from steer_llm_sdk.orchestration import Orchestrator, OrchestrationConfig

orchestrator = Orchestrator()

result = await orchestrator.run(
    request={"query": "Analyze feasibility"},
    tool_name="feasibility_bundle",
    tool_options={"k": 3, "epsilon": 0.2},
    options=OrchestrationConfig(
        max_parallel=10,
        budget={"tokens": 2000, "cost_usd": 0.10},
        streaming=True
    )
)

# Access Evidence Bundle
if "evidence_bundle" in result.content:
    bundle = result.content["evidence_bundle"]
    print(f"Confidence: {bundle['summary']['confidence']}")
    print(f"Cost: ${result.metadata['cost_usd']:.4f}")
```

## Orchestrator Types

### Basic Orchestrator

Direct tool execution with explicit tool selection.

```python
from steer_llm_sdk.orchestration import Orchestrator

orchestrator = Orchestrator()
result = await orchestrator.run(
    request="Analyze this",
    tool_name="analyzer_tool"
)
```

### Reliable Orchestrator

Automatic tool selection with retry logic, circuit breakers, and idempotency.

```python
from steer_llm_sdk.orchestration import ReliableOrchestrator

orchestrator = ReliableOrchestrator()
result = await orchestrator.run(
    request={"type": "analysis", "data": "..."},
    options=OrchestrationConfig(
        idempotency_key="unique-123",
        trace_id="trace-456"
    )
)
# Planner selects best tool automatically
```

## Tool Architecture

Tools encapsulate domain-specific logic:

```python
from steer_llm_sdk.orchestration import BundleTool, BundleOptions, EvidenceBundle

class MyBundleTool(BundleTool):
    @property
    def name(self) -> str:
        return "my_bundle"

    async def _execute_bundle(
        self,
        request: dict,
        options: BundleOptions,
        event_manager=None
    ) -> EvidenceBundle:
        # Run K parallel executions
        # Return Evidence Bundle with statistics
        pass
```

## Evidence Bundles

Tools return Evidence Bundles containing:
- Raw replicates from parallel executions
- Consensus and disagreements
- Pairwise distances
- Confidence scores

```python
{
    "meta": {"k": 3, "epsilon": 0.2},
    "replicates": [{"output": "..."}, ...],
    "summary": {
        "consensus": {...},
        "disagreements": [...],
        "confidence": 0.95
    }
}
```

## Streaming Events

Tools emit progress events:

```python
# Tool execution events
- tool_started
- replicate_started
- replicate_done
- partial_summary  (after K=2)
- bundle_ready
- error, timeout, cancelled
```

## Budget Management

Budgets are checked after execution completes:

```python
result = await orchestrator.run(
    request="Analyze",
    tool_name="analyzer",
    options=OrchestrationConfig(
        budget={
            "tokens": 1000,
            "cost_usd": 0.10,
            "time_ms": 30000
        }
    )
)
# Raises BudgetExceeded if limits exceeded
```

## Reliability Features

### Retry Logic

```python
from steer_llm_sdk.orchestration.reliability import ReliabilityConfig, RetryPolicy

config = ReliabilityConfig(
    retry_policy=RetryPolicy(
        max_attempts=3,
        backoff_factor=2.0,
        respect_retry_after=True
    )
)

orchestrator = ReliableOrchestrator(reliability_config=config)
```

### Circuit Breakers

```python
from steer_llm_sdk.reliability import CircuitBreakerConfig

config = ReliabilityConfig(
    circuit_breaker_configs={
        "openai": CircuitBreakerConfig(
            failure_threshold=5,
            timeout=60.0
        )
    }
)
```

### Idempotency

```python
# Prevent duplicate execution
result = await orchestrator.run(
    request={"query": "Important"},
    options=OrchestrationConfig(
        idempotency_key="unique-request-123"
    )
)
# Repeat with same key returns cached result
```

## Best Practices

1. **Tool Design**: Keep tools focused on specific domains
2. **Replicate Strategy**: Start with K=2, add K=3 only if needed
3. **Resource Management**: Set per-replicate budgets conservatively
4. **Integration**: Register tools at application startup
5. **Idempotency**: Use idempotency keys for critical operations
6. **Monitoring**: Track circuit breaker states and error rates

## See Also

- [Current State](CURRENT_STATE.md) - Implementation status
- [Planning & Reliability Guide](planning-reliability-guide.md) - Advanced features
- [API Reference](../orchestration.md) - Detailed API documentation
