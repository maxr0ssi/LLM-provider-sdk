# Layered-Modular Architecture - Phase Tracker

## Overview
This document tracks the progress of refactoring the Steer LLM SDK to a layered-modular architecture. The refactoring aims to create clear separation of concerns, enable easy addition of new providers/models, maintain backward compatibility and finally allow full agent use -- using external SDK Agent packages e.g. Open AI.

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

### Phase 2: Capability Registry Hardening 🟡
**Status**: IN PROGRESS
**Target**: 1-2 weeks
**Dependencies**: Phase 1 complete

#### Tasks:
- [ ] 2.1 Capability Audit (verify all shipped models’ flags: supports_json_schema, supports_temperature, fixed_temperature, uses_max_completion_tokens, supports_seed, supports_prompt_caching)
- [ ] 2.2 Capability-Driven Routing (ensure router/policy paths rely only on capabilities, no name heuristics)
- [ ] 2.3 Provider Capability Handling (providers reference normalization + capabilities consistently; remove any residual name checks)

#### Detailed Plan (Phase 2)

- Objectives
  - Ensure the Capability Registry is the single source of truth for behavior (param names, temperature rules, schema support, seed, streaming, prompt caching, pricing fields).
  - Eliminate all model-name or provider-specific heuristics from parameter mapping and routing; use capabilities only.
  - Document and test capability-driven policies across all shipped models.

- Scope
  - OpenAI models: `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-4o`, `gpt-4o-mini`, `o4-mini` (and versioned aliases used in tests).
  - Anthropic: active test models (e.g., `claude-3-haiku*`, `claude-3-5-haiku*`).
  - xAI: current adapter targets.
  - Pricing fields alignment (input/output/cached input per 1K tokens) for cost calc.

- Out of scope
  - Adding new providers or non-tested model families (tracked in backlog).
  - Changing public API.

- Deliverables
  - Completed capability entries for all shipped models (flags + pricing consistency).
  - `core/capabilities/policy.py` helper(s):
    - `map_max_tokens_field(capabilities, provider) -> {max_tokens|max_completion_tokens|max_output_tokens}`
    - `apply_temperature_policy(params, capabilities) -> temperature|omit`
    - `should_use_responses_api(params, capabilities) -> bool` (if not already sufficient)
  - Removal of residual name checks in normalization (e.g., `"gpt-5-mini" in model_id.lower()`).
  - Tests: unit coverage per model for mapping; smoke spot-checks.
  - Docs: capability table excerpt + guidance (architecture-plan.md link).

- Work Breakdown
  1) Inventory & audit (Day 1)
     - Enumerate `MODEL_CONFIGS` and map to capabilities; list gaps/inconsistencies.
     - Verify token parameter naming per model family (`uses_max_completion_tokens`, Responses API `max_output_tokens`).
     - Verify temperature support and any fixed/required temperatures.
     - Verify `supports_json_schema`, `supports_seed`, `supports_prompt_caching`.
  2) Implement policy helpers (Day 2)
     - Add `core/capabilities/policy.py` with helpers noted above.
     - Refactor `core/normalization/params.py` to use helpers instead of name checks.
  3) Provider integration (Day 3)
     - Ensure OpenAI/Anthropic/xAI adapters consume normalized params without local name heuristics.
     - Keep Responses API path selection strictly capability-driven.
  4) Pricing alignment (Day 3)
     - Confirm input/output/cached pricing in configs for cost calc.
  5) Tests (Day 4)
     - Unit tests: parameter mapping per model; temperature omission/clamp; seeds conditional.
     - Ensure JSON schema path uses `text.format` and enforces `additionalProperties=false`.
  6) Docs (Day 4)
     - Add capability notes to `architecture-plan.md` and update examples where helpful.

- Acceptance Criteria
  - Zero model-name heuristics in normalization/adapters; capabilities-only mapping.
  - All capability flags accurate for shipped models; tests encode expectations.
  - Cost calculations use consistent pricing fields; cache savings computed where applicable.
  - All tests green.

- Risks & Mitigations
  - Provider SDK drift → mitigate with capability gates and unit tests.
  - Versioned model IDs → normalize to base IDs in capability lookup.
  - Mock gaps → harden adapters with getattr/try/except as already established.

- Owners & Timeline
  - Owner: SDK Core
  - Duration: ~4 days as outlined (can parallelize audit/tests while adding policy helpers).

### Phase 3: Provider Adapter Clean Split 🔴
**Status**: NOT STARTED  
**Target**: 1-2 weeks
**Dependencies**: Phase 1.1, Phase 2

#### Tasks:
- [ ] 3.1 Isolate Provider Logic (ensure adapters don’t perform cross-provider logic; centralize to normalization/policy)
- [ ] 3.2 Logging Standardization (structured logging; provider tag; debug vs info policy)
- [ ] 3.3 Error Handling Consistency (typed ProviderError mapping; retryable classification)

### Phase 4: Streaming & Events 🔴
**Status**: NOT STARTED
**Target**: 1 week
**Dependencies**: Phase 1.4, Phase 3

#### Tasks:
- [ ] 4.1 StreamAdapter Enhancement (normalize deltas across providers; JSON vs text; end-of-stream usage finalization)
- [ ] 4.2 Event Consistency (emit on_start/on_delta/on_complete/on_error uniformly; optional metrics hooks)

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
- [ ] 7.1 OpenAI Agents SDK Adapter

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
- ⏳ Compatibility shims in place (main.py → api/client.py)

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

## Change Log

### 2025-08-13
- Created phase tracker document
- Started Phase 1 implementation  
- Set up agent-architecture branch
- **CRITICAL**: Identified need for directory restructuring
- Added Phase 0.5 for restructuring (blocks all other work)
- Updated Phase 1 status to BLOCKED
- Created RESTRUCTURING_PLAN.md with detailed migration strategy
- **Progress Update (PM)**:
  - ✅ Completed provider restructuring (0.5.3)
    - Moved all providers to new `providers/` structure
    - Created migration script `migrate_providers.sh`
    - Updated all imports successfully
  - ✅ Completed main.py compatibility shim (0.5.5)
    - Moved `SteerLLMClient` to `api/client.py`
    - Created deprecation warnings
    - Verified backward compatibility
  - Phase 0.5 now at 40% completion

### 2025-08-14
- Completed Phase 0.5 directory restructuring
- Moved core normalization/capabilities/routing into `core/`
- Created `streaming/` and `reliability/` layers with new modules
- Isolated providers under top-level `providers/`
- Added `observability/` with metrics and sinks
- Updated import paths and shims; all tests green
- Documentation updated and migration notes added
  - Removed legacy shims: `steer_llm_sdk/main.py`, `steer_llm_sdk/LLMConstants.py`, `steer_llm_sdk/llm/*`

### 2025-08-14
- Completed Phase 1: Contracts & Normalization
- ✅ All providers now inherit from ProviderAdapter base class
- ✅ Integrated normalize_params() and normalize_usage() into all providers
- ✅ Resolved duplicate ProviderCapabilities definitions
- ✅ Fixed OpenAI Responses API parameter handling
- ✅ Created helper method _build_responses_api_payload() for consistent API calls
- ✅ Fixed transform_messages_for_provider to use "input" instead of "messages" for Responses API
- ✅ Updated test mocks to provide proper usage data structures
- ✅ All unit tests passing (20/20)
- ✅ All smoke tests passing (8/8)
- Phase 1 now at 100% completion

## Current Status Summary

**Current Focus**: Phase 2 (Capability Registry Hardening) ready to begin

### Phase 1 Achievements:
1. Clean provider abstraction with ProviderAdapter interface
2. Consistent parameter normalization across all providers
3. Standardized usage reporting format
4. Improved Responses API support
5. Capability-driven behavior throughout

### Next Immediate Steps:
1. Begin Phase 2: Capability Registry Hardening
2. Complete capability definitions for all models
3. Implement capability-driven routing
4. Remove any remaining hardcoded provider logic

### Work Completed in Phase 1:
- ✅ ProviderAdapter base class in `providers/base.py`
- ✅ Usage normalization in `core/normalization/usage.py`
- ✅ Parameter normalization in `core/normalization/params.py`
- ✅ Updated GenerationParams in `models/generation.py`
- ✅ All providers updated and tested

---

Last Updated: 2025-08-14
Next Review: After Phase 2 progress