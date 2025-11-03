# Orchestration API Reference

Quick reference for the orchestration API.

## Client Methods

### register_tool

```python
client.register_tool(tool: Tool) -> None
```

Register a tool with the global registry.

### list_tools

```python
client.list_tools() -> Dict[str, Dict[str, Any]]
```

List all registered tools with metadata (version, description, capabilities).

## Orchestrators

### Orchestrator

Basic orchestrator for direct tool execution.

```python
from steer_llm_sdk.orchestration import Orchestrator

orchestrator = Orchestrator()

result = await orchestrator.run(
    request={"query": "Analyze this"},
    tool_name="analysis_tool",
    tool_options={"k": 3},
    options=OrchestrationConfig(
        max_parallel=10,
        budget={"tokens": 2000}
    )
)
```

### ReliableOrchestrator

Advanced orchestrator with automatic tool selection, retry logic, and circuit breakers.

```python
from steer_llm_sdk.orchestration import ReliableOrchestrator

orchestrator = ReliableOrchestrator()

# Tool automatically selected by planner
result = await orchestrator.run(
    request={"type": "analysis", "data": "..."},
    options=OrchestrationConfig(
        idempotency_key="unique-123",
        trace_id="trace-456"
    )
)
```

## Configuration

### OrchestrationConfig

```python
OrchestrationConfig(
    max_parallel: int = 10,
    timeout_ms: Optional[int] = None,
    budget: Optional[Dict] = None,  # {"tokens": 2000, "cost_usd": 0.10}
    streaming: bool = False,
    idempotency_key: Optional[str] = None,
    trace_id: Optional[str] = None
)
```

### ReliabilityConfig

```python
ReliabilityConfig(
    max_retries: int = 3,
    initial_delay_ms: int = 1000,
    max_delay_ms: int = 60000,
    exponential_base: float = 2.0
)
```

## Tool Interface

### Tool

```python
from steer_llm_sdk.orchestration import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    async def execute(
        self,
        request: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        event_manager = None
    ) -> Any:
        # Implementation
        pass
```

### BundleTool

For parallel execution with Evidence Bundles:

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
        event_manager = None
    ) -> EvidenceBundle:
        # Run K parallel executions
        # Return Evidence Bundle with statistics
        pass
```

### BundleOptions

```python
BundleOptions(
    k: int = 3,              # Number of parallel executions
    epsilon: float = 0.2,    # Early stopping threshold
    max_parallel: int = 10,  # Concurrency limit
    schema_uri: Optional[str] = None
)
```

## Output Models

### OrchestrationOutput

```python
class OrchestrationOutput:
    content: Any                    # Tool result
    usage: Dict[str, Any]          # Token/cost usage
    metadata: Dict[str, Any]       # Additional metadata
    trace_id: str                  # Trace identifier
    elapsed_ms: int                # Execution time
    status: str                    # "completed", "failed", etc.
```

### EvidenceBundle

```python
class EvidenceBundle:
    replicates: List[Replicate]    # Individual executions
    summary: BundleSummary         # Aggregate statistics
```

### BundleSummary

```python
class BundleSummary:
    consensus: Dict[str, Any]           # Consensus result
    disagreements: List[Disagreement]   # Points of disagreement
    confidence: float                   # Statistical confidence
```

## Errors

- `OrchestratorError` - Base orchestration error
- `ToolExecutionError` - Tool execution failed
- `BudgetExceeded` - Resource limit exceeded
- `ConflictError` - Idempotency conflict

## Events

Tools can emit events via EventManager:
- `tool_started`, `replicate_started`, `replicate_done`
- `partial_summary`, `bundle_ready`
- `warning`, `error`, `timeout`, `cancelled`

See [orchestration guides](orchestration/) for detailed usage examples.
