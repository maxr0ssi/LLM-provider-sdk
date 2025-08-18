# Steer LLM SDK v0.3.2 Release Notes

## Release Date: 2025-08-18

## Overview

Version 0.3.2 introduces the production-ready **Orchestration Module**, providing tool-based orchestration with advanced reliability features. This release completes the integration of the M0 and M1 orchestration phases, delivering a clean, professional architecture for executing complex LLM operations.

## 🚀 Major Features

### Tool-Based Orchestration Architecture

The SDK now provides a powerful orchestration system where orchestrators delegate to registered tools:

- **Tool Registry**: Host applications can register domain-specific tools
- **Evidence Bundles**: Statistical analysis of parallel executions with raw replicates + computed statistics
- **Bundle Tools**: Handle parallel execution, validation, and analysis
- **Streaming Events**: Real-time progress updates tagged with tool names
- **SDK Methods**: New `register_tool()` and `list_tools()` client methods

```python
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.orchestration import Orchestrator

# Register tools
client = SteerLLMClient()
client.register_tool(MyCustomTool())

# Execute via orchestrator
orchestrator = Orchestrator()
result = await orchestrator.run(
    request={"query": "Analyze this"},
    tool_name="my_tool",
    tool_options={"k": 3, "epsilon": 0.2}
)
```

### Planning & Reliability Features

The new `ReliableOrchestrator` provides production-grade reliability:

#### Automatic Tool Selection
- Rule-based planner selects appropriate tools
- Type-based rules and keyword matching
- Budget-aware selection
- Circuit breaker state awareness

#### Reliability Features
- **Retry Logic**: Exponential backoff with jitter
- **Circuit Breakers**: Per-provider protection with configurable thresholds
- **Error Classification**: Intelligent retry decisions
- **Automatic Fallback**: Alternative tool selection on failures

#### Idempotency Support
- Request deduplication via idempotency keys
- Conflict detection for mismatched payloads
- Per-tool key derivation
- TTL-based caching

#### Distributed Tracing
- Automatic trace/request ID generation
- ID propagation through all layers
- Tool-level context preservation

```python
from steer_llm_sdk.orchestration import ReliableOrchestrator

orchestrator = ReliableOrchestrator()
result = await orchestrator.run(
    request={"type": "analysis", "data": "..."},
    # No tool specified - planner selects best tool
    options=OrchestrationConfig(
        idempotency_key="unique-request-123",
        trace_id="trace-456"
    )
)
```

## 🧹 Major Cleanup

This release includes a comprehensive cleanup of the orchestration module:

### Removed
- All backwards compatibility code
- Milestone references (M0/M1/M2/M3)
- Legacy naming conventions

### Renamed Classes
- `EnhancedOrchestrator` → `ReliableOrchestrator`
- `OrchestratorOptions` → `OrchestrationConfig`
- `OrchestratorResult` → `OrchestrationOutput`
- `PlanningContext` → `PlanRequest`
- `PlanningResult` → `PlanDecision`
- `BundleMeta` → `BundleMetadata`
- `EnhancedRetryManager` → `AdvancedRetryManager`

### Renamed Files
- `orchestrator_v2.py` → `reliable_orchestrator.py`

### Code Consolidation
- Created `BaseOrchestrator` to eliminate duplicate code
- Unified error handling patterns
- Consistent naming throughout

## 📊 Test Coverage

- **32 orchestration tests** all passing (100% success rate)
- Tool-based orchestration: 8/8 tests ✅
- Planner selection: 14/14 tests ✅
- Reliability features: 11/11 tests ✅

## 📚 Documentation

Comprehensive documentation for the orchestration module:

- [Orchestration Overview](docs/orchestration/overview.md) - Architecture and usage
- [Current State](docs/orchestration/CURRENT_STATE.md) - Detailed module state
- [Planning & Reliability Guide](docs/orchestration/planning-reliability-guide.md) - Advanced features
- [Tool Development Guide](docs/orchestration/tool-development-guide.md) - Creating custom tools
- [Evidence Bundle Guide](docs/orchestration/evidence-bundle-guide.md) - Statistical analysis

## 💔 Breaking Changes

While the module is new, users upgrading from pre-release versions should update:

- Import paths: `orchestrator_v2` → `reliable_orchestrator`
- Class names as listed above
- No backwards compatibility shims are provided

## 🔧 Installation

```bash
# From GitHub Package Registry
pip install steer-llm-sdk --index-url https://${GITHUB_TOKEN}@github.com/maxr0ssi/LLM-provider-sdk/releases/download/v0.3.2/

# From source
pip install git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.2

# With all features
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.2#egg=steer-llm-sdk[openai-agents,tiktoken,http]"
```

## 🎯 What's Next

Future enhancements being considered:
- Persistent idempotency store (currently in-memory)
- Distributed circuit breakers for multi-instance deployments
- ML-based tool selection strategies
- Prometheus/OpenTelemetry metrics integration
- Tool versioning support

## 🙏 Acknowledgments

Thanks to the team for the comprehensive testing and feedback during the orchestration module development.

---

For questions or issues, please:
- Create an issue on [GitHub](https://github.com/maxr0ssi/LLM-provider-sdk/issues)
- Contact the Steer team at support@steer.ai