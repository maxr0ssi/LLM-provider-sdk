# Layered-Modular Architecture - Phase Tracker

## Overview
This document tracks the progress of refactoring the Steer LLM SDK to a layered-modular architecture. The refactoring aims to create clear separation of concerns, enable easy addition of new providers/models, maintain backward compatibility and finally allow full agent use -- using external SDK Agent packages e.g. Open AI.

**Documentation Organization**: Completed phase documentation has been moved to `completed-phases/` subdirectories for better organization.

**CRITICAL UPDATE (2025-08-13)**: Added Phase 0.5 for directory restructuring. The current directory structure does not reflect the layered architecture, making it difficult to implement clean separation. Restructuring must happen BEFORE continuing with other phases. New modules to scaffold during this phase: `streaming/types.py`, `reliability/budget.py`.

## Phase Status Legend
- 🟢 COMPLETE
- 🟡 IN PROGRESS  
- 🔴 NOT STARTED
- 🔵 BLOCKED
- ⚪ FUTURE

## Phase Timeline

### Phase 0: Baseline Validation 🟢
**Status**: COMPLETE (2025-08-13)
- ✅ All smoke tests passing
- ✅ v0.2.1 released with Nexus agent framework
- ✅ Public API snapshot documented

### Phase 0.5: Directory Restructuring 🟢
**Status**: COMPLETE (2025-08-14)  
**Target**: 1 week  
**Progress**: 100%  
**Priority**: CRITICAL - Completed; unblocks Phase 1

#### Rationale:
Current structure mixes concerns and doesn't reflect layered architecture:
- Providers buried under `llm/providers/`
- Normalization under `llm/` instead of its own layer
- No clear separation between layers
- Difficult to trace request flow through layers

#### New Structure:
```
steer_llm_sdk/
├── api/                    # Public API Layer
├── core/                   # Core Logic Layers
│   ├── decision/          # Decision & Normalization
│   ├── normalization/     # Parameter/Usage/Stream normalization
│   ├── capabilities/      # Capability registry & policies
│   └── routing/           # Provider routing
├── providers/             # Provider Adapters (isolated)
├── streaming/             # Streaming & Events Layer
├── reliability/           # Errors, Retries, Idempotency
├── observability/         # Metrics & Monitoring
├── agents/                # Agent Framework
├── models/                # Shared data models
├── config/                # Configuration
└── integrations/          # Optional native adapters
```

#### Tasks:
- [x] 0.5.1 Create New Directory Structure
  - [x] Create api/, core/, providers/, streaming/, reliability/, observability/, integrations/
  - [x] Add __init__.py files across new packages
  - [x] Create `core/LAYER_README.md`
  - [x] Scaffold `streaming/types.py` and `reliability/budget.py`

- [x] 0.5.2 Move Core Components
  - [x] Move normalization to `core/normalization/`
  - [x] Move capabilities to `core/capabilities/`
  - [x] Move routing logic to `core/routing/`
  - [x] Update all imports

- [x] 0.5.3 Restructure Providers
  - [x] Move providers to top-level `providers/`
  - [x] Create provider-specific subdirectories (openai/, anthropic/, xai/)
  - [x] Move base adapter class (`llm/base.py` → `providers/base.py`)
  - [x] Update provider imports in router and client paths
  - [x] Update tests/mocks for new paths

- [x] 0.5.4 Move Support Systems
  - [x] Move streaming components → `streaming/adapter.py`, `streaming/manager.py`
  - [x] Move reliability components → `reliability/errors.py`, `reliability/retry.py`, `reliability/idempotency.py`, `reliability/budget.py`
  - [x] Move observability components → `observability/metrics.py`, `observability/sinks/`

- [x] 0.5.5 Compatibility Layer
  - [x] Create import shims for backward compatibility
  - [x] Make `main.py` a shim that re-exports from `api/client.py`
  - [x] Add deprecation warnings for direct `main.py` imports
  - [x] Verify backward compatibility with tests
  - [x] Update documentation and add migration notes

### Phase 1: Contracts & Normalization 🟢
**Status**: COMPLETE (2025-08-14)  
**Target**: 1 week (reduced from 2 weeks)  
**Progress**: 100%  
**Dependencies**: Phase 0.5 COMPLETE

#### Completed Work:
- ✅ Created ProviderAdapter base class in `providers/base.py`
- ✅ Created usage normalization in `core/normalization/usage.py`
- ✅ Created parameter normalization in `core/normalization/params.py`
- ✅ Updated GenerationParams with new fields
- ✅ All providers updated to inherit from ProviderAdapter
- ✅ All providers using normalization functions
- ✅ Resolved duplicate ProviderCapabilities definitions
- ✅ Fixed Responses API parameter handling
- ✅ All tests passing (unit and smoke tests)

#### Tasks Completed:
- [x] 1.1 Provider Adapter Interface
  - [x] Create base abstract class ✅
  - [x] Move to correct location (providers/base.py) ✅
  - [x] Update all providers to inherit ✅
  - [x] Document interface contract ✅

- [x] 1.2 Usage Normalization
  - [x] Create usage normalizer module ✅
  - [x] Implement normalize_usage function ✅
  - [x] Move to core/normalization/ ✅
  - [x] Update all providers to use it ✅
  - [x] Add comprehensive tests ✅

- [x] 1.3 Parameter Normalization  
  - [x] Create params normalizer module ✅
  - [x] Implement capability-based mapping ✅
  - [x] Move to core/normalization/ ✅
  - [x] Update providers to use normalizers ✅
  - [x] Test parameter transformations ✅

- [x] 1.4 Streaming Event Normalization
  - [x] Basic streaming normalization in place ✅
  - [x] Standardize on_usage timing ✅
  - [x] Update provider streaming ✅
  - [x] Document streaming contract ✅

- [x] 1.5 Integration
  - [x] GenerationParams updated ✅
  - [x] Wire normalizers into providers ✅
  - [x] Remove old hardcoded logic ✅
  - [x] Verify consistency across providers ✅

### Phase 2: Capability Registry Hardening 🟢
**Status**: COMPLETE (2025-08-15)
**Target**: 1-2 weeks
**Progress**: 100%
**Dependencies**: Phase 1 complete

#### Tasks Completed
- [x] 2.1 Capability Audit (verify all shipped models' flags: supports_json_schema, supports_temperature, fixed_temperature, uses_max_completion_tokens, supports_seed, supports_prompt_caching)
- [x] 2.2 Capability-Driven Routing (ensure router/policy paths rely only on capabilities, no name heuristics)
- [x] 2.3 Provider Capability Handling (providers reference normalization + capabilities consistently; remove any residual name checks)

### Phase 3: Provider Adapter Clean Split 🟢
**Status**: COMPLETE (2025-08-15) — Reviewed and Verified
**Target**: 1–2 weeks  
**Dependencies**: Phase 2 complete

#### Tasks Completed
- [x] Adapter audit and cleanup (OpenAI/Anthropic/xAI)
- [x] Logging standard applied across adapters (structured ProviderLogger)
- [x] Unified error mapping to ProviderError with retry classification
- [x] Streaming consistency via StreamAdapter (normalized deltas; single usage emission)
- [x] Conformance tests per adapter (generate, stream, stream_with_usage)

#### Acceptance Criteria
- [x] No cross-provider logic in adapters; policy/normalization lives in core
- [x] Structured logs include provider/model/request_id consistently
- [x] ProviderError mapping consistent and covered by tests
- [x] Conformance tests pass for OpenAI, Anthropic, xAI

#### Risks & Mitigations
- Upstream SDK changes → minimize per-adapter logic; rely on core helpers; cover with unit tests
- Streaming event variance → encapsulate normalization in `StreamAdapter`; finalize usage in router when needed

### Phase 4: Streaming & Events 🟢
**Status**: COMPLETE (2025-08-15)
**Target**: 1 week (Actual: 7 days)
**Dependencies**: Phase 1.4, Phase 3 ✅

#### Summary:
Phase 4 successfully implemented a comprehensive streaming infrastructure with JSON handling, usage aggregation, and event processing. All components are fully integrated and tested end-to-end.

#### Key Deliverables:
- ✅ **JsonStreamHandler**: Robust JSON parsing with <0.3ms per chunk overhead
- ✅ **UsageAggregator**: Accurate token counting with tiktoken and character-based fallback
- ✅ **EventProcessor**: Flexible filtering and transformation pipeline with <1ms overhead
- ✅ **StreamingOptions**: Clean configuration model with presets
- ✅ **Full Integration**: All providers support streaming options, JSON handling, and events
- ✅ **Documentation**: Complete guides and migration instructions

#### Tasks:
- [x] 4.1 StreamAdapter Enhancement (normalize deltas across providers; JSON vs text; end-of-stream usage finalization)
  - [x] JsonStreamHandler implementation with full JSON parsing
  - [x] StreamAdapter integration with JSON awareness
  - [x] StreamingOptions configuration model
  - [x] Client API updated with streaming options
  - [x] End-of-stream usage finalization patterns (via UsageAggregator)
- [x] 4.2 Event Consistency (emit on_start/on_delta/on_complete/on_error uniformly; optional metrics hooks)

#### Progress:
**Day 1-2 (COMPLETE):**
- ✅ Created `JsonStreamHandler` in `streaming/json_handler.py`
  - Handles nested JSON and arrays
  - Streaming validation and repair
  - Excellent performance: < 0.1ms for simple objects
- ✅ Integrated JSON handler with StreamAdapter
  - `set_response_format()` method
  - JSON detection and processing
  - Metrics integration
- ✅ Created StreamingOptions configuration
  - Consolidates all streaming settings
  - Preset configurations (JSON_MODE, DEBUG, HIGH_PERFORMANCE)
  - Backward compatible with legacy parameters
- ✅ Updated client API
  - `stream_with_usage` accepts StreamingOptions
  - Auto-enables JSON mode for json_object response format
  - Legacy `enable_json_stream_handler` parameter supported
- ✅ Comprehensive testing
  - 20 unit tests for JsonStreamHandler
  - 16 edge case tests
  - 10 StreamAdapter integration tests
  - 7 provider-specific JSON streaming tests
  - Performance benchmarks show < 0.3ms per chunk

**Day 3-4 (COMPLETE):**
- ✅ Created `UsageAggregator` in `streaming/aggregator.py`
  - Base class with standard interface
  - TiktokenAggregator for accurate OpenAI counting
  - CharacterAggregator with provider-specific ratios
  - Confidence scoring for estimation accuracy
- ✅ Integrated aggregator with StreamAdapter
  - `configure_usage_aggregation()` method
  - Automatic chunk tracking
  - Metrics integration
- ✅ Updated xAI provider
  - Now uses aggregator instead of simple division
  - Respects StreamingOptions configuration
  - Better accuracy (65% confidence vs 50%)
- ✅ Enhanced StreamingOptions
  - Added aggregator_type and prefer_tiktoken options
  - Works with existing presets
- ✅ Comprehensive testing
  - 22 unit tests for aggregators
  - 13 accuracy tests
  - 12 integration tests
  - Performance benchmarks

**Day 5 (COMPLETE):**
- ✅ Created `EventProcessor` in `streaming/processor.py`
  - Base class with filtering and transformation pipeline
  - TypeFilter, ProviderFilter, PredicateFilter, CompositeFilter
  - CorrelationTransformer, TimestampTransformer, MetricsTransformer
  - Background processing support
- ✅ Created `BatchedEventProcessor` for efficient event batching
  - Configurable batch size and timeout
  - Async batch handler support
  - Automatic flush on completion
- ✅ Created typed event models in `models/events.py`
  - StreamEvent base class
  - StreamStartEvent, StreamDeltaEvent, StreamUsageEvent, StreamCompleteEvent, StreamErrorEvent
  - Rich metadata support
- ✅ Integrated EventProcessor with StreamAdapter
  - `set_event_processor()` method for configuration
  - Automatic event emission during streaming lifecycle
  - Provider/model/request_id metadata injection
  - Usage and error event support
- ✅ Comprehensive testing
  - 23 unit tests for EventProcessor
  - 7 integration tests for StreamAdapter events
  - All tests passing with <1ms event processing overhead

**Day 6 (COMPLETE):**
- ✅ Enhanced EventManager with typed event support
  - Updated to support both typed and untyped callbacks
  - Added emit_event method for typed event dispatch
  - Backward compatible with legacy callbacks
- ✅ Updated StreamingHelper for typed events
  - All helper methods now use typed events
  - Async adapter methods properly integrated
  - Error events include retry information
- ✅ Updated all providers for consistent event emission
  - OpenAI, Anthropic, and xAI adapters updated
  - Event processor configuration from streaming options
  - Proper async start_stream, track_chunk, complete_stream calls
  - Usage event emission integrated
- ✅ Added event callbacks to client API
  - stream_with_usage accepts on_start, on_delta, on_usage, on_complete, on_error
  - Automatic EventManager and EventProcessor creation
  - Seamless integration with streaming options
- ✅ Created comprehensive tests and documentation
  - Integration tests for event system
  - Type hierarchy tests
  - Complete streaming events guide with examples
  - Migration guide for existing users

**Integration Completion (2025-08-15):**
- ✅ Fixed provider adapters to properly read StreamingOptions
- ✅ Updated client to use JSON handler output instead of heuristic
- ✅ Added final JSON pass-through in provider responses
- ✅ Fixed Pydantic v2 compatibility issues
- ✅ All integration tests passing

#### Documentation:
All Phase 4 documentation has been organized in `completed-phases/phase-4/`:
- PHASE_4_PLAN.md - Initial planning document
- PHASE_4_TECHNICAL_DESIGN.md - Detailed technical design
- PHASE_4_SUMMARY.md - Research and proposal summary
- PHASE_4_DAY1_2_SUMMARY.md - JSON handler implementation
- PHASE_4_DAY3_4_SUMMARY.md - Usage aggregator implementation
- PHASE_4_DAY5_SUMMARY.md - Event processor implementation
- PHASE_4_DAY6_SUMMARY.md - Event system integration
- PHASE_4_INTEGRATION_SUMMARY.md - Final integration completion

### Phase 5: Reliability Layer 🔴
**Status**: NOT STARTED
**Target**: 1 week  
**Dependencies**: Phase 3.3

#### Tasks:
- [ ] 5.1 Error Type Verification (audit errors across providers; map to reliability/errors)
- [ ] 5.2 Retry Manager Testing (transient failure injection; backoff policy; streaming initial connect retries)

### Phase 6: Metrics & Documentation 🔴
**Status**: NOT STARTED
**Target**: 1 week
**Dependencies**: Phase 1-5

#### Tasks:
- [ ] 6.1 Metrics Implementation (observability/collector; OTLP sink example; in-memory sink; streaming metrics)
- [ ] 6.2 Documentation Updates (guides for Responses API, streaming split, determinism, pricing/config)

### Phase 7: Optional Adapters 🔴
**Status**: NOT STARTED
**Target**: 2-3 weeks
**Dependencies**: Phase 1-6 complete

#### Tasks:
- [ ] 7.1 OpenAI Agents SDK Adapter !

### Phase 8: Testing & Validation 🔴
**Status**: NOT STARTED
**Target**: 1 week
**Dependencies**: Phase 1-7

#### Tasks:
- [ ] 8.1 Backward Compatibility Tests
- [ ] 8.2 Integration Tests

## Success Criteria

### Code Quality Metrics
- ✅ All files < 400 LOC
- ⏳ No hardcoded provider logic in core
- ⏳ Clean layer separation achieved

### Functionality Metrics  
- ✅ All existing tests pass
- ⏳ New provider addition < 2 hours
- ⏳ New model addition < 30 minutes

### Performance Metrics
- ✅ No response time regression
- ✅ Streaming latency unchanged
- ✅ Memory usage stable

### Documentation Metrics
- ⏳ All interfaces documented
- ⏳ Extension guides complete
- ⏳ Migration guide available
- ⏳ Layer READMEs created

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking API changes | High | backward compatibility testing |
| Provider API drift | Medium | Version pinning, adapter isolation |
| Performance regression | Medium | Benchmarking before/after |
| Complexity increase | Low | Clear documentation, examples |

#### Work Completed in Phase 3 (Day 1-4):
- ✅ Created structured logging utility in `observability/logging.py`
  - Tracks requests with unique IDs
  - Logs usage metrics
  - Provides performance tracking
- ✅ Created error mapping utilities in `providers/errors.py`
  - Maps provider-specific errors to standardized ProviderError
  - Determines retryable errors
  - Extracts retry-after headers
- ✅ Enhanced ProviderError class with retryable flags
- ✅ Updated RetryManager with provider-aware retry logic
- ✅ Cleaned up all three provider adapters:
  - Removed hardcoded prompt caching logic (now uses capability-based policy helpers)
  - Removed cost calculation logic (belongs in router/core)
  - Added structured logging with request tracking
  - Updated error handling to use ErrorMapper
  - Fixed parameter normalization usage
- ✅ All adapters now properly use:
  - `get_cache_control_config()` for prompt caching decisions
  - `normalize_params()` for parameter mapping
  - `normalize_usage()` for usage standardization
  - Structured logging with ProviderLogger
- ✅ Enhanced StreamAdapter with provider-specific normalization (Day 3):
  - Added provider-specific delta normalization methods
  - Added usage extraction and aggregation support
  - Added streaming metrics tracking (chunks, duration, chars/sec)
  - Created StreamDelta.get_text() method for easy text extraction
- ✅ Created StreamingHelper for common patterns:
  - `collect_with_usage()` for collecting all chunks with metrics
  - `stream_with_events()` for streaming with EventManager integration
- ✅ Added typed event classes for EventManager:
  - StreamStartEvent, StreamDeltaEvent, StreamUsageEvent, StreamCompleteEvent
- ✅ Updated all provider adapters to use enhanced StreamAdapter:
  - OpenAI, Anthropic, and xAI all use StreamAdapter for normalization
  - Removed duplicate streaming logic from providers
  - Added streaming metrics logging to all providers
- ✅ Created streaming conformance tests in `tests/conformance/test_streaming_conformance.py`
- ✅ Created comprehensive conformance test suite (Day 4):
  - `test_generation_conformance.py` - Tests generate() method consistency
  - `test_error_conformance.py` - Tests error handling and retry classification
  - `test_parameter_conformance.py` - Tests parameter normalization and mapping
  - `test_usage_conformance.py` - Tests usage data normalization
  - Enhanced streaming tests with edge cases (empty streams, interruptions, long streams)
  - Created shared fixtures in `conftest.py` for all conformance tests


  Change log moved to: docs/architecture/projects/layered-modular/change-log.md