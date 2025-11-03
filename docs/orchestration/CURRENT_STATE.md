# Orchestration Module - Current State

Production-ready tool-based architecture for executing LLM operations with advanced reliability features.

## Architecture

### Core Components

1. **BaseOrchestrator** (`base.py`)
   - Abstract base class with shared functionality
   - Handles result processing, budget checking, event emission

2. **Orchestrator** (`orchestrator.py`)
   - Basic orchestrator implementation
   - Direct tool execution without planning
   - Supports streaming, timeouts, and budget constraints

3. **ReliableOrchestrator** (`reliable_orchestrator.py`)
   - Advanced orchestrator with planning and reliability features
   - Automatic tool selection via planner
   - Retry logic with exponential backoff
   - Circuit breaker protection
   - Idempotency support

### Tool System

- Tools are registered in a global registry
- Tools execute the actual LLM operations
- Tools can return Evidence Bundles for statistical analysis
- Tools are discovered and selected by the planner

### Planning System

- **Planner** (`planning/planner.py`) - Base planner interface
- **RuleBasedPlanner** (`planning/rule_based.py`) - Rule-based tool selection
  - Matches requests against configured rules
  - Considers circuit breaker states
  - Provides fallback tool selection

### Reliability Features

1. **Retry Management**
   - Exponential backoff with jitter
   - Respects rate limit retry-after headers
   - Error classification for smart retries

2. **Circuit Breakers**
   - Per-provider circuit breakers
   - Automatic failure detection
   - Integration with planning system

3. **Idempotency**
   - Request deduplication via idempotency keys
   - Conflict detection for mismatched requests
   - In-memory cache with TTL

## Key Classes

### Configuration
- `OrchestrationConfig` - Runtime options for orchestration
- `ReliabilityConfig` - Reliability feature configuration
- `CircuitBreakerConfig` - Circuit breaker thresholds

### Models
- `OrchestrationOutput` - Result of orchestration
- `EvidenceBundle` - Statistical analysis results
- `BundleMetadata` - Metadata about bundle execution
- `PlanRequest` - Context for planning decisions
- `PlanDecision` - Result of planning process

### Errors
- `OrchestratorError` - Base orchestration error
- `ToolExecutionError` - Tool-specific failures
- `BudgetExceeded` - Resource limit violations
- `ConflictError` - Idempotency conflicts

## Status

### Completed
- All backwards compatibility code removed
- All milestone references (M0/M1/M2) cleaned up
- Version suffixes eliminated
- Duplicate code consolidated via inheritance
- All 32 orchestration tests passing

### Test Coverage
- Tool-based orchestration: 8/8 tests passing
- Planner selection: 14/14 tests passing
- Reliability features: 11/11 tests passing

## Usage Examples

### Basic Orchestration
```python
from steer_llm_sdk.orchestration import Orchestrator, OrchestrationConfig

orchestrator = Orchestrator()
result = await orchestrator.run(
    request="Analyze this text",
    tool_name="text_analyzer",
    options=OrchestrationConfig(
        max_parallel=5,
        budget={"tokens": 1000}
    )
)
```

### Reliable Orchestration with Planning
```python
from steer_llm_sdk.orchestration import ReliableOrchestrator

orchestrator = ReliableOrchestrator()
result = await orchestrator.run(
    request={"type": "analysis", "data": "..."},
    # No tool specified - planner will select
    options=OrchestrationConfig(
        idempotency_key="unique-request-123",
        trace_id="trace-456"
    )
)
```

## Migration from Pre-Cleanup Versions

Update class names:
- `EnhancedOrchestrator` → `ReliableOrchestrator`
- `OrchestratorOptions` → `OrchestrationConfig`
- `OrchestratorResult` → `OrchestrationOutput`
- `PlanningContext` → `PlanRequest`
- `PlanningResult` → `PlanDecision`
