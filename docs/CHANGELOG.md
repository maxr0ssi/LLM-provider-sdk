# Changelog

All notable changes to the Steer LLM SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-08-13 (still in pogress)
### Changed
- Completed Phase 0.5 directory restructuring (2025-08-14)
  - Introduced new layered structure: `api/`, `core/`, `providers/`, `streaming/`, `reliability/`, `observability/`, `integrations/`
  - Moved normalization/capabilities/routing under `core/`
  - Isolated providers to top-level `providers/`
  - Added streaming and reliability layers and modules
  - Maintained backward compatibility via shims (`main.py`)
  - Updated documentation and migration notes

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