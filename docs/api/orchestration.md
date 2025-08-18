# Orchestration API Reference

## Overview

The orchestration API provides methods for registering tools and executing complex LLM operations with reliability features.

## Client Methods

### register_tool

Register a tool with the global tool registry.

```python
client.register_tool(tool: Tool) -> None
```

**Parameters:**
- `tool`: An instance implementing the `Tool` interface

**Example:**
```python
from steer_llm_sdk import SteerLLMClient
from my_tools import AnalysisTool

client = SteerLLMClient()
client.register_tool(AnalysisTool())
```

### list_tools

List all registered tools with their metadata.

```python
client.list_tools() -> Dict[str, Dict[str, Any]]
```

**Returns:**
Dictionary mapping tool names to their metadata including version, description, and capabilities.

**Example:**
```python
tools = client.list_tools()
print(tools)
# {
#   'analysis_tool': {
#     'version': '1.0.0',
#     'description': 'Performs domain analysis',
#     'supports_bundle': True
#   }
# }
```

## Orchestrator Classes

### Orchestrator

Basic orchestrator for direct tool execution.

```python
from steer_llm_sdk.orchestration import Orchestrator

orchestrator = Orchestrator()
```

#### run

Execute a tool with the given request.

```python
async def run(
    self,
    request: Union[str, Dict[str, Any]],
    tool_name: Optional[str] = None,
    tool_options: Optional[Dict[str, Any]] = None,
    options: Optional[OrchestrationConfig] = None,
    agents: Optional[List[AgentDefinition]] = None
) -> OrchestrationOutput
```

**Parameters:**
- `request`: The request data (string or dictionary)
- `tool_name`: Name of the tool to execute (required for basic orchestrator)
- `tool_options`: Tool-specific options (e.g., k, epsilon, schema_uri)
- `options`: Orchestration configuration
- `agents`: List of agents (deprecated, use tools instead)

**Returns:**
`OrchestrationOutput` with content, usage, metadata, and status.

**Example:**
```python
result = await orchestrator.run(
    request={"query": "Analyze feasibility"},
    tool_name="feasibility_tool",
    tool_options={"k": 3, "epsilon": 0.2},
    options=OrchestrationConfig(
        max_parallel=10,
        budget={"tokens": 2000}
    )
)
```

### ReliableOrchestrator

Advanced orchestrator with planning and reliability features.

```python
from steer_llm_sdk.orchestration import ReliableOrchestrator

orchestrator = ReliableOrchestrator(
    planner=None,  # Uses default RuleBasedPlanner
    reliability_config=None  # Uses default config
)
```

Inherits all methods from `Orchestrator` and adds:
- Automatic tool selection when `tool_name` not specified
- Retry logic with exponential backoff
- Circuit breaker protection
- Idempotency support
- Trace ID propagation

**Example:**
```python
# Tool automatically selected by planner
result = await orchestrator.run(
    request={"type": "analysis", "data": "..."},
    options=OrchestrationConfig(
        idempotency_key="unique-123",
        trace_id="trace-456"
    )
)
```

## Configuration Classes

### OrchestrationConfig

Configuration options for orchestration execution.

```python
class OrchestrationConfig(BaseModel):
    max_parallel: int = 10
    timeout_ms: Optional[int] = None
    budget: Optional[Dict[str, Union[int, float]]] = None
    streaming: bool = False
    metadata: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    trace_id: Optional[str] = None
    request_id: Optional[str] = None
```

**Fields:**
- `max_parallel`: Maximum concurrent executions
- `timeout_ms`: Overall timeout in milliseconds
- `budget`: Resource limits (tokens, cost_usd, time_ms)
- `streaming`: Enable event streaming
- `metadata`: Additional metadata to include
- `idempotency_key`: Key for request deduplication
- `trace_id`: Distributed trace identifier
- `request_id`: Unique request identifier

### ReliabilityConfig

Configuration for reliability features (ReliableOrchestrator only).

```python
class ReliabilityConfig(BaseModel):
    max_retries: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 60000
    exponential_base: float = 2.0
    jitter: bool = True
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    idempotency_ttl_ms: int = 3600000  # 1 hour
```

## Tool Interfaces

### Tool

Base interface for all tools.

```python
from abc import ABC, abstractmethod

class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        pass
    
    @property
    def version(self) -> str:
        """Tool version."""
        return "1.0.0"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return ""
    
    @abstractmethod
    async def execute(
        self,
        request: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        event_manager: Optional[EventManager] = None
    ) -> Any:
        """Execute the tool."""
        pass
```

### BundleTool

Specialized tool for parallel execution with Evidence Bundles.

```python
from steer_llm_sdk.orchestration import BundleTool, BundleOptions, EvidenceBundle

class MyBundleTool(BundleTool):
    @property
    def name(self) -> str:
        return "my_bundle_tool"
    
    async def _execute_bundle(
        self,
        request: Dict[str, Any],
        options: BundleOptions,
        event_manager: Optional[EventManager] = None
    ) -> EvidenceBundle:
        # Implementation
        pass
```

### BundleOptions

Options for bundle tools.

```python
class BundleOptions(BaseModel):
    k: int = 3
    seeds: Optional[List[int]] = None
    epsilon: float = 0.2
    schema_uri: Optional[str] = None
    max_parallel: int = 10
    per_replicate_budget: Optional[Dict[str, Any]] = None
    global_budget: Optional[Dict[str, Any]] = None
```

## Models

### OrchestrationOutput

Result of orchestration execution.

```python
class OrchestrationOutput(BaseModel):
    content: Any
    usage: Dict[str, Any]
    metadata: Dict[str, Any]
    trace_id: str
    request_id: str
    elapsed_ms: int
    status: str = "completed"
    errors: Optional[Dict[str, Any]] = None
```

### EvidenceBundle

Statistical analysis of parallel executions.

```python
class EvidenceBundle(BaseModel):
    meta: BundleMetadata
    replicates: List[Replicate]
    summary: BundleSummary
```

### BundleSummary

Summary statistics for Evidence Bundle.

```python
class BundleSummary(BaseModel):
    consensus: Dict[str, Any]
    disagreements: List[Disagreement]
    pairwise_distance: List[List[float]]
    confidence: float
```

## Event Types

Tools can emit the following events via `EventManager`:

- `tool_started` - Tool execution begins
- `replicate_started` - Individual replicate starts
- `replicate_done` - Replicate completes
- `partial_summary` - Statistics after K=2
- `bundle_ready` - Final Evidence Bundle ready
- `warning` - Validation or other warnings
- `error` - Tool execution error
- `timeout` - Execution timeout
- `cancelled` - Execution cancelled

## Error Types

### OrchestratorError

Base error for orchestration failures.

```python
class OrchestratorError(Exception):
    """Base orchestration error."""
    pass
```

### ToolExecutionError

Tool-specific execution failure.

```python
class ToolExecutionError(OrchestratorError):
    """Tool execution failed."""
    def __init__(self, tool_name: str, error: Exception):
        self.tool_name = tool_name
        self.error = error
```

### BudgetExceeded

Resource budget exceeded.

```python
class BudgetExceeded(OrchestratorError):
    """Budget limit exceeded."""
    def __init__(self, budget_type: str, limit: Any, actual: Any):
        self.budget_type = budget_type
        self.limit = limit
        self.actual = actual
```

### ConflictError

Idempotency conflict detected.

```python
class ConflictError(OrchestratorError):
    """Idempotency conflict."""
    def __init__(self, key: str, message: str):
        self.key = key
        super().__init__(f"Conflict for key {key}: {message}")
```

## Complete Example

```python
import asyncio
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.orchestration import (
    ReliableOrchestrator,
    OrchestrationConfig,
    BundleTool,
    BundleOptions,
    EvidenceBundle
)

# Define a custom bundle tool
class AnalysisBundleTool(BundleTool):
    @property
    def name(self) -> str:
        return "analysis_bundle"
    
    async def _execute_bundle(
        self,
        request: Dict[str, Any],
        options: BundleOptions,
        event_manager=None
    ) -> EvidenceBundle:
        # Run K parallel analyses
        # Return Evidence Bundle with statistics
        pass

async def main():
    # Initialize client and register tool
    client = SteerLLMClient()
    client.register_tool(AnalysisBundleTool())
    
    # Create reliable orchestrator
    orchestrator = ReliableOrchestrator()
    
    # Execute with automatic tool selection
    result = await orchestrator.run(
        request={
            "type": "analysis",
            "query": "Analyze market trends"
        },
        options=OrchestrationConfig(
            budget={"tokens": 5000, "cost_usd": 0.50},
            idempotency_key="analysis-123",
            streaming=True
        )
    )
    
    # Process Evidence Bundle
    if "evidence_bundle" in result.content:
        bundle = result.content["evidence_bundle"]
        print(f"Confidence: {bundle['summary']['confidence']}")
        print(f"Consensus: {bundle['summary']['consensus']}")
        print(f"Cost: ${result.metadata['cost_usd']:.4f}")

if __name__ == "__main__":
    asyncio.run(main())
```