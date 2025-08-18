# Changelog

All notable changes to the Steer LLM SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2025-08-18

### Added
- **Orchestration Module**: Production-ready tool-based orchestration system
  - Tool Registry for host applications to register domain-specific tools
  - Evidence Bundle format with raw replicates + computed statistics
  - Bundle tools handle parallel execution, validation, and analysis
  - Built-in interfaces: `Tool`, `BundleTool`, `EvidenceBundle`
  - Example `SimpleBundleTool` demonstrating the pattern
  - Streaming events tagged with tool names and progress updates
  - SDK client methods: `register_tool()` and `list_tools()`
  - Tools internally use `runtime="openai_agents"` (no fallbacks)
  - Comprehensive test coverage for new architecture
  - See [Orchestration Guide](./orchestration/overview.md) for usage

- **Orchestration Planning & Reliability**: Production-grade enhancements
  - **Automatic Tool Selection**: Rule-based planner selects appropriate tools
    - Type-based rules, keyword matching, budget-aware selection
    - Circuit breaker state awareness in planning
    - Fallback tool support with priority ordering
  - **Reliability Features**: Production-grade error handling
    - Retry with exponential backoff and jitter
    - Per-provider circuit breakers with configurable thresholds
    - Error classification for intelligent retry decisions
    - Automatic fallback to alternative tools
  - **Idempotency Support**: Request deduplication
    - Conflict detection for same key with different payload
    - Per-tool idempotency keys derived from request key
    - Configurable TTL-based caching
  - **Trace Propagation**: Distributed tracing support
    - Automatic trace/request ID generation
    - ID propagation through all layers
    - Tool-level context preservation
  - New `ReliableOrchestrator` class with planning and reliability features
  - See [Planning & Reliability Guide](./orchestration/planning-reliability-guide.md) for usage

### Changed
- **Orchestration Module - Major Cleanup**: Production-ready refactoring
  - Removed all backwards compatibility and legacy code
  - Eliminated milestone references (M0/M1/M2/M3)
  - Renamed classes for professional naming:
    - `EnhancedOrchestrator` → `ReliableOrchestrator`
    - `OrchestratorOptions` → `OrchestrationConfig`
    - `OrchestratorResult` → `OrchestrationOutput`
    - `PlanningContext` → `PlanRequest`
    - `PlanningResult` → `PlanDecision`
    - `BundleMeta` → `BundleMetadata`
    - `EnhancedRetryManager` → `AdvancedRetryManager`
  - Renamed `orchestrator_v2.py` to `reliable_orchestrator.py`
  - Created `BaseOrchestrator` to consolidate duplicate code
  - Fixed IdempotencyManager interface (added async wrappers)
  - Fixed retry backoff test expectations
  - Fixed circuit breaker state mapping for planner
  - All 32 orchestration tests now passing (100% success rate)
  - See [CURRENT_STATE.md](./orchestration/CURRENT_STATE.md) for details

## [0.3.1] - 2025-08-16
### Security
- **BREAKING**: API keys are now passed directly to the `SteerLLMClient` constructor instead of being read from environment variables
  - This improves security by ensuring the SDK repository contains no keys
  - API keys can still fall back to environment variables for backward compatibility

### Changed
- Updated `SteerLLMClient` to accept `openai_api_key`, `anthropic_api_key`, and `xai_api_key` parameters
- Modified all provider adapters to accept API keys in their constructors
- Removed global provider instances - providers are now created with API keys
- Updated router to check provider availability based on configured API keys

### Example
```python
from steer_llm_sdk import SteerLLMClient

# Pass API keys directly (recommended)
client = SteerLLMClient(
    openai_api_key="your-openai-key",
    anthropic_api_key="your-anthropic-key",
    xai_api_key="your-xai-key"
)

# Or still use environment variables (backward compatible)
client = SteerLLMClient()  # Will read from OPENAI_API_KEY, etc.
```

## [0.3.0] - 2025-08-16
### Changed
- Completed Phase 0.5 directory restructuring (2025-08-14)
  - Introduced new layered structure: `api/`, `core/`, `providers/`, `streaming/`, `reliability/`, `observability/`, `integrations/`
  - Moved normalization/capabilities/routing under `core/`
  - Isolated providers to top-level `providers/`
  - Added streaming and reliability layers and modules
  - Maintained backward compatibility via shims (`main.py`)
  - Updated documentation and migration notes
  - Removed legacy shims in follow-up commit (0.3.0 cycle):
    - `steer_llm_sdk/main.py` re-export removed; use `steer_llm_sdk.api.client`
    - `steer_llm_sdk/LLMConstants.py` removed; use `steer_llm_sdk.config.constants`
    - legacy `steer_llm_sdk/llm/*` shims removed; use new layer paths

## [0.2.1] - 2025-08-13
### Fixed
- Added missing `steer_llm_sdk/models` directory to git (was incorrectly ignored)
- Fixed .gitignore to not exclude code directories named "models"
- Resolved import errors from missing conversation_types and generation modules

## [0.2.0] - 2025-08-13

### Added
- **Nexus Agent Framework**: Complete implementation of agent-based architecture
  - `AgentDefinition`, `AgentOptions`, and `AgentResult` models
  - `AgentRunner` with streaming callbacks and event management
  - Deterministic execution with centralized parameter control
  - Idempotency support with TTL-based deduplication
  
- **OpenAI Responses API Support**
  - Full integration for GPT-4.1-mini and GPT-5-mini models
  - Automatic routing between Chat Completions and Responses API
  - Proper handling of GPT-5-mini temperature requirements
  - Native JSON schema validation support
  
- **Provider Capabilities System**
  - Capability-driven routing replacing hardcoded model checks
  - Comprehensive feature detection per model
  - Support for fixed temperature requirements (e.g., o4-mini)
  
- **JSON Schema Validation**
  - Strict schema validation with detailed error messages
  - Schema repair and extraction tools
  - Support for both native and post-hoc validation
  
- **Tool Framework**
  - Local deterministic tool execution
  - Built-in tools: `format_validator`, `extract_json`, `json_repair`
  - JSON schema generation from Python callables
  
- **Error Handling and Metrics**
  - Typed errors: `ProviderError`, `SchemaError`, `TimeoutError`, etc.
  - Retry manager for transient failures
  - Pluggable metrics sink with OpenTelemetry support

### Changed
- Updated GPT-5-mini pricing to correct values
- Removed `cost_per_1k_tokens` field in favor of exact pricing
- Improved logging throughout (removed print statements)
- Normalized usage tracking across all providers
- Enhanced streaming with unified callback interface

### Fixed
- Proper handling of OpenAI cached token pricing
- Correct parameter mapping for different model types
- Streaming usage data collection

### Documentation
- Comprehensive SDK architecture documentation
- OpenAI Responses API usage guide
- Agent framework examples and migration notes
- Reorganized documentation structure

## [0.1.2] - 2025-06-28

### Added
- Initial multi-provider support (OpenAI, Anthropic, xAI)
- Basic streaming capabilities
- Cost calculation framework

### Changed
- Improved error handling
- Enhanced type safety with Pydantic

### Fixed
- Various bug fixes in provider implementations