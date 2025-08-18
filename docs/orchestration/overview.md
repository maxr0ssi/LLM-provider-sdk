# Orchestration Overview

The orchestration module provides a tool-based architecture for executing complex LLM operations with advanced reliability features. The module uses a clean, production-ready design where orchestrators delegate to registered tools that encapsulate domain-specific logic, parallel execution, and statistical analysis.

## Key Features

- **Tool-Based Architecture**: Modular design with pluggable tools
- **Automatic Planning**: Smart tool selection based on request characteristics
- **Reliability Features**: Retry logic, circuit breakers, and idempotency
- **Evidence Bundles**: Statistical analysis of parallel executions
- **Streaming Support**: Real-time event streaming for long operations
- **Budget Management**: Token and cost constraints

## Quick Start

### 1. Register Tools (Host Application)

```python
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.orchestration.tools.examples import SimpleBundleTool
from my_app.tools import FeasibilityBundleTool  # Your custom tool

# Initialize SDK
client = SteerLLMClient()

# Register tools at startup
client.register_tool(SimpleBundleTool())
client.register_tool(FeasibilityBundleTool())

# List available tools
print(client.list_tools())
# {'simple_bundle': {'version': '1.0.0', ...}, 'feasibility_bundle': {...}}
```

### 2. Execute Tools via Orchestrator

```python
from steer_llm_sdk.orchestration import Orchestrator, OrchestrationConfig

# Create orchestrator
orchestrator = Orchestrator()

# Execute a tool
result = await orchestrator.run(
    request={"query": "Analyze feasibility of quantum computing"},
    tool_name="feasibility_bundle",
    tool_options={
        "k": 3,  # Run 3 replicates
        "epsilon": 0.2,  # Early stop threshold
        "schema_uri": "https://schemas.example.com/feasibility.json"
    },
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
    print(f"Disagreements: {bundle['summary']['disagreements']}")
    print(f"Total cost: ${result.cost_usd:.4f}")
```

## Orchestrator Types

The module provides two orchestrator implementations:

### 1. Basic Orchestrator
- Direct tool execution without planning
- Suitable when you know which tool to use
- Supports all core features (streaming, budgets, timeouts)

```python
from steer_llm_sdk.orchestration import Orchestrator

orchestrator = Orchestrator()
result = await orchestrator.run(
    request="Analyze this",
    tool_name="analyzer_tool"  # Explicit tool selection
)
```

### 2. Reliable Orchestrator
- Automatic tool selection via planner
- Built-in reliability features (retry, circuit breakers)
- Idempotency support for distributed systems
- Recommended for production use

```python
from steer_llm_sdk.orchestration import ReliableOrchestrator

orchestrator = ReliableOrchestrator()
result = await orchestrator.run(
    request={"type": "analysis", "data": "..."}
    # No tool specified - planner selects best tool
)
```

## Key Features

### Tool-Based Architecture
- Tools encapsulate complex operations (parallel execution, validation, statistics)
- Host applications implement domain-specific tools
- SDK provides infrastructure and interfaces

### Evidence Bundles
- Tools return Evidence Bundles with raw replicates + computed statistics
- Includes consensus, disagreements, pairwise distances, confidence scores
- Orchestrator consumes atomic bundles for reasoning

### Streaming Support
- Tools emit progress events (replicate_done, partial_summary, bundle_ready)
- Events tagged with tool name and metadata
- Real-time updates for UI/monitoring

### Resource Management
- Global and per-replicate budgets (tokens, time, cost)
- Early stopping based on confidence thresholds
- Budget enforcement and audit trails

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Orchestrator                       │
│  ┌─────────────────────────────────────────────┐   │
│  │              Tool Registry                   │   │
│  │  • SimpleBundleTool                         │   │
│  │  • FeasibilityBundleTool                    │   │
│  │  • ScoringBundleTool                        │   │
│  └─────────────────────────────────────────────┘   │
│                         ↓                           │
│  ┌─────────────────────────────────────────────┐   │
│  │           Selected Tool Execution            │   │
│  │  • Parallel replicates (K=3)                │   │
│  │  • Schema validation                        │   │
│  │  • Statistical analysis                     │   │
│  └─────────────────────────────────────────────┘   │
│                         ↓                           │
│  ┌─────────────────────────────────────────────┐   │
│  │            Evidence Bundle                   │   │
│  │  • Raw replicates                           │   │
│  │  • Consensus & disagreements                │   │
│  │  • Confidence scores                        │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Tool Interface

### Base Tool Class

```python
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name"""
    
    @abstractmethod
    async def execute(
        self,
        request: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        event_manager: Optional[EventManager] = None
    ) -> Any:
        """Execute the tool"""
```

### Bundle Tool Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `k` | int | 3 | Number of replicates to run |
| `seeds` | List[int] | Auto | Random seeds for replicates |
| `epsilon` | float | 0.2 | Early stop threshold |
| `schema_uri` | str | None | JSON schema for validation |
| `max_parallel` | int | 10 | Maximum concurrent replicates |
| `per_replicate_budget` | dict | None | Budget per replicate |
| `global_budget` | dict | None | Global budget across all |

## Evidence Bundle Schema

```json
{
  "meta": {
    "task": "feasibility",
    "k": 3,
    "model": "gpt-4o-mini",
    "seeds": [11, 23, 47],
    "early_stopped": false
  },
  "replicates": [
    {
      "id": "r1",
      "data": { /* validated output */ },
      "quality": { "valid": true },
      "usage": { "total_tokens": 150 }
    },
    // ... more replicates
  ],
  "summary": {
    "consensus": { /* agreed fields */ },
    "disagreements": [
      { "field": "risk_level", "values": ["high", "medium"] }
    ],
    "pairwise_distance": [[0, 0.2], [0.2, 0]],
    "confidence": 0.85
  }
}
```

## Tool Event Types

- `bundle_started` - Tool execution begins
- `replicate_done` - Individual replicate completes
- `partial_summary` - Summary after K=2 (for early stop)
- `bundle_ready` - Final Evidence Bundle ready
- `warning` - Validation errors or truncation
- `timeout` / `cancelled` - Execution interrupted

## Error Handling

The orchestrator handles tool execution errors gracefully:

```python
try:
    result = await orchestrator.run(
        request={"query": "test"},
        tool_name="my_tool"
    )
except ValueError:
    # Tool not found
    print("Tool not registered")

if result.status == "failed":
    # Tool execution failed
    error = result.errors["my_tool"]
    print(f"Error: {error['message']}")
    print(f"Error code: {error['code']}")
    print(f"Retryable: {error['is_retryable']}")
```

## Implementing a Bundle Tool

```python
from steer_llm_sdk.orchestration import BundleTool, BundleOptions, EvidenceBundle

class MyBundleTool(BundleTool):
    @property
    def name(self) -> str:
        return "my_bundle"
    
    async def _execute_bundle(
        self,
        request: Dict[str, Any],
        options: BundleOptions,
        event_manager: Optional[EventManager] = None
    ) -> EvidenceBundle:
        # 1. Run K replicates in parallel
        replicates = await self._run_replicates(request, options)
        
        # 2. Validate outputs
        self._validate_outputs(replicates, options.schema_uri)
        
        # 3. Compute statistics
        summary = self._compute_statistics(replicates)
        
        # 4. Check early stop
        if options.k > 2 and summary.confidence >= (1 - options.epsilon):
            # Skip K=3 if confidence is high
            pass
        
        # 5. Return Evidence Bundle
        return EvidenceBundle(
            meta=BundleMeta(...),
            replicates=replicates,
            summary=summary
        )
```

## Best Practices

1. **Tool Design**
   - Keep tools focused on specific domains (feasibility, scoring, etc.)
   - Implement proper schema validation
   - Compute meaningful statistics for the domain

2. **Replicate Strategy**
   - Use diverse seeds/prompts for better coverage
   - Start with K=2 and add K=3 only if needed
   - Set epsilon based on acceptable confidence

3. **Resource Management**
   - Set per-replicate budgets conservatively
   - Use global budgets as circuit breakers
   - Monitor early stop effectiveness

4. **Integration**
   - Register tools at application startup
   - Use consistent naming conventions
   - Version tools for compatibility

## Runtime Requirements

- Tools internally use `AgentRunner` with `runtime="openai_agents"`
- No fallback runtimes supported
- Python 3.10+ with asyncio support
- Host applications implement domain-specific tools

## Planning & Reliability Features

The enhanced orchestrator (`reliable_orchestrator.py`) adds production-grade features:

### Automatic Tool Selection
- Rule-based planner selects appropriate tools
- Considers request type, keywords, budget constraints
- Respects circuit breaker states

### Reliability Features
- **Retry Logic**: Exponential backoff with configurable policies
- **Circuit Breakers**: Per-provider protection against failures
- **Fallback Tools**: Automatic failover to alternative tools
- **Error Classification**: Intelligent retry decisions

### Idempotency & Tracing
- Request deduplication with conflict detection
- Automatic trace/request ID generation and propagation
- Per-tool idempotency keys

See the [Planning & Reliability Guide](./planning-reliability-guide.md) for detailed usage.

## Implementation Notes

### Budget Semantics

Budgets are **post-run checks only**. The orchestrator:
- Does NOT divide budgets among sub-agents
- Does NOT preemptively stop agents based on budget
- Checks budgets AFTER all agents complete
- Raises `BudgetExceeded` if limits are exceeded
- Includes the configured budget in result metadata for auditability

```python
# Budget is checked after execution completes
result = await orchestrator.run(
    request,
    agents,
    OrchestrationConfig(budget={"tokens": 1000})
)
# result.metadata['budget'] will contain {"tokens": 1000}
```

### Idempotency Behavior

The orchestrator implements idempotency with:
- Each sub-agent gets a unique key: `{orchestrator_key}_{agent_name}`
- Full conflict detection at orchestrator level (with planning & reliability features)
- Conflict detection also delegated to individual sub-agents

### Error Contract

All error objects include a standardized `code` field:

```python
{
    "type": "TimeoutError",
    "message": "Agent timed out after 5000ms",
    "is_retryable": true,
    "code": "TIMEOUT"  # Standardized error code
}
```

Error codes:
- `TIMEOUT` - Agent exceeded time limit
- `AGENT_FAILED` - Generic agent failure
- `UNKNOWN_ERROR` - Unexpected error type

## See Also

- [Current State](./CURRENT_STATE.md) - Implementation status
- [Planning & Reliability Guide](./planning-reliability-guide.md) - Advanced features
- [API Reference](../api/orchestration.md) - Detailed API documentation