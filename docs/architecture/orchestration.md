# Orchestration Architecture

## Overview

The orchestration layer provides a tool-based architecture for executing complex LLM operations with advanced reliability features. It sits between the Public API layer and the Decision & Normalization layer, coordinating multi-step operations across tools and providers.

## Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          User Application                           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SteerLLMClient API                           │
│  • register_tool(tool) / list_tools()                               │
│  • Orchestrator / ReliableOrchestrator                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Orchestration Layer                           │
├─────────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐     │
│  │ Tool Registry  │  │    Planner     │  │ Reliability Manager│     │
│  │                │  │                │  │                    │     │
│  │ • Discovery    │  │ • Rule-based   │  │ • Retry logic      │     │
│  │ • Validation   │  │ • Tool match   │  │ • Circuit breakers │     │
│  │ • Metadata     │  │ • Fallbacks    │  │ • Error classify   │     │
│  └────────────────┘  └────────────────┘  └────────────────────┘     │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │                    Tool Execution Engine                   │     │
│  │                                                            │     │
│  │  • Parallel execution management                           │     │
│  │  • Budget enforcement (tokens/cost/time)                   │     │
│  │  • Event streaming and progress tracking                   │     │
│  │  • Idempotency with conflict detection                     │     │
│  │  • Trace/request ID propagation                            │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │                 Evidence Bundle Aggregator                 │     │
│  │                                                            │     │
│  │  • Raw replicate collection                                │     │
│  │  • Statistical analysis (consensus, disagreements)         │     │
│  │  • Confidence scoring                                      │     │
│  │  • Early stopping logic (epsilon threshold)                │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────┐
│                           Registered Tools                         │
├─────────────────────────┬─────────────────────┬────────────────────┤
│   SimpleBundleTool      │  FeasibilityTool    │   CustomTool       │
│                         │                     │                    │
│ • K replicates          │ • Domain logic      │ • User defined     │
│ • Schema validation     │ • Custom analysis   │ • Any operation    │
│ • Statistical summary   │ • Specialized stats │ • Flexible output  │
└─────────────────────────┴─────────────────────┴────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent Runner (via Tools)                         │
│  • Tools internally use runtime="openai_agents"                     │
│  • No fallback runtimes supported                                   │
│  • Structured output via JSON schema                                │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### Tool Registry
- Global registry for tool discovery and management
- Tools are registered at application startup
- Each tool has unique name, version, and metadata
- Registry validates tool interfaces on registration

### Planner (ReliableOrchestrator only)
- Rule-based tool selection engine
- Matches requests against configured rules:
  - Type-based matching (e.g., type="analysis" → analysis_tool)
  - Keyword matching in request content
  - Budget constraints (prefer cheaper tools)
  - Circuit breaker awareness (skip broken tools)
- Provides fallback tool selection
- Estimates costs and duration

### Reliability Manager
- **Retry Logic**
  - Exponential backoff with jitter
  - Respects rate limit retry-after headers
  - Configurable max attempts and delays
  - Error classification for smart retries

- **Circuit Breakers**
  - Per-provider circuit breakers
  - States: CLOSED → OPEN → HALF_OPEN
  - Configurable failure thresholds
  - Automatic recovery with half-open testing

- **Error Classification**
  - Rate limit errors → retry with backoff
  - Timeout errors → retry immediately
  - Schema errors → no retry
  - Provider errors → check circuit breaker

### Tool Execution Engine
- Manages concurrent tool executions
- Enforces resource budgets:
  - Token limits (per-replicate and global)
  - Cost limits in USD
  - Time limits with timeouts
- Streams events in real-time:
  - `tool_started` - Execution begins
  - `replicate_done` - Individual replicate completes
  - `partial_summary` - Early statistics (K=2)
  - `bundle_ready` - Final results available
- Handles idempotency:
  - Deduplicates requests by key
  - Detects conflicts (same key, different payload)
  - Per-tool key derivation: `{orchestrator_key}_{tool_name}`

### Evidence Bundle Aggregator
- Collects raw outputs from parallel replicates
- Computes statistical summaries:
  - **Consensus**: Fields where all replicates agree
  - **Disagreements**: Fields with varying values
  - **Pairwise distances**: Similarity matrix
  - **Confidence score**: Overall agreement metric
- Supports early stopping:
  - Check confidence after K=2
  - Skip K=3 if confidence > (1 - epsilon)
  - Configurable epsilon threshold

## Data Flow

1. **Request arrives** at orchestrator with optional tool name
2. **Planning phase** (if ReliableOrchestrator and no tool specified):
   - Planner analyzes request characteristics
   - Selects best tool based on rules
   - Considers circuit breaker states
3. **Execution phase**:
   - Tool retrieved from registry
   - Idempotency check performed
   - Tool.execute() called with options
4. **Tool processing**:
   - Bundle tools run K parallel replicates
   - Each replicate uses AgentRunner
   - Progress events streamed
5. **Result aggregation**:
   - Evidence Bundle created with statistics
   - Orchestrator wraps in OrchestrationOutput
   - Metadata includes costs, timing, trace IDs

## Key Design Decisions

### Tool-Based Architecture
- **Separation of Concerns**: Orchestrator coordinates, tools execute
- **Pluggability**: Easy to add new tools without changing core
- **Domain Specificity**: Tools encapsulate domain logic
- **Reusability**: Tools can be shared across applications

### Evidence Bundles
- **Transparency**: Raw outputs preserved alongside statistics
- **Statistical Rigor**: Multiple metrics for confidence assessment
- **Early Stopping**: Efficiency through adaptive execution
- **Schema Validation**: Structured outputs with guarantees

### Reliability First
- **Production Ready**: Built for real-world conditions
- **Graceful Degradation**: Fallbacks and circuit breakers
- **Observability**: Comprehensive event streaming
- **Idempotency**: Safe for distributed systems

## Integration Points

### With SDK Layers
- **Public API**: Exposes orchestration methods and tool registry
- **Agent Layer**: Tools use AgentRunner internally
- **Streaming Layer**: Events flow through streaming infrastructure
- **Metrics Layer**: Usage and performance metrics collected
- **Error Layer**: Typed errors with retry classifications

### With Applications
- **Tool Registration**: Apps register tools at startup
- **Request Handling**: Apps call orchestrator.run()
- **Event Processing**: Apps can subscribe to progress events
- **Result Consumption**: Apps receive Evidence Bundles

## Future Enhancements

1. **Persistent State**
   - Database-backed idempotency store
   - Distributed circuit breaker state
   - Historical execution analytics

2. **Advanced Planning**
   - ML-based tool selection
   - Cost optimization strategies
   - Multi-tool workflow composition

3. **Enhanced Observability**
   - OpenTelemetry integration
   - Prometheus metrics export
   - Distributed tracing spans

4. **Tool Ecosystem**
   - Tool marketplace/registry
   - Tool versioning and compatibility
   - Tool composition patterns