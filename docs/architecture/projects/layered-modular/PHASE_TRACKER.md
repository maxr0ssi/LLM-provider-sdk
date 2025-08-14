# Layered-Modular Architecture - Phase Tracker

## Overview
This document tracks the progress of refactoring the Steer LLM SDK to a layered-modular architecture. The refactoring aims to create clear separation of concerns, enable easy addition of new providers/models, and maintain backward compatibility.

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

### Phase 1: Contracts & Normalization 🟡
**Status**: IN PROGRESS (unblocked by Phase 0.5)  
**Target**: 1 week (reduced from 2 weeks)  
**Progress**: 0%  
**Dependencies**: Phase 0.5 COMPLETE

#### Completed Work (in wrong structure):
- ✅ Created ProviderAdapter base class in `llm/base.py`
- ✅ Created usage normalization in `llm/normalizers/usage.py`
- ✅ Created parameter normalization in `llm/normalizers/params.py`
- ✅ Updated GenerationParams with new fields

#### Remaining Tasks (to do AFTER restructuring):
- [ ] 1.1 Provider Adapter Interface
  - [x] Create base abstract class ✅
  - [ ] Move to correct location (providers/base.py)
  - [ ] Update all providers to inherit
  - [ ] Document interface contract

- [ ] 1.2 Usage Normalization
  - [x] Create usage normalizer module ✅
  - [x] Implement normalize_usage function ✅
  - [ ] Move to core/normalization/
  - [ ] Update all providers to use it
  - [ ] Add comprehensive tests

- [ ] 1.3 Parameter Normalization  
  - [x] Create params normalizer module ✅
  - [x] Implement capability-based mapping ✅
  - [ ] Move to core/normalization/
  - [ ] Update providers to use normalizers
  - [ ] Test parameter transformations

- [ ] 1.4 Streaming Event Normalization
  - [ ] Create streaming normalization module
  - [ ] Standardize on_usage timing
  - [ ] Update provider streaming
  - [ ] Document streaming contract

- [ ] 1.5 Integration
  - [x] GenerationParams updated ✅
  - [ ] Wire normalizers into providers
  - [ ] Remove old hardcoded logic
  - [ ] Verify consistency across providers

### Phase 2: Capability Registry Hardening 🔴
**Status**: NOT STARTED
**Target**: 1-2 weeks
**Dependencies**: Phase 1.3

#### Tasks:
- [ ] 2.1 Capability Audit
- [ ] 2.2 Capability-Driven Routing
- [ ] 2.3 Provider Capability Handling

### Phase 3: Provider Adapter Clean Split 🔴
**Status**: NOT STARTED  
**Target**: 1-2 weeks
**Dependencies**: Phase 1.1, Phase 2

#### Tasks:
- [ ] 3.1 Isolate Provider Logic
- [ ] 3.2 Logging Standardization
- [ ] 3.3 Error Handling Consistency

### Phase 4: Streaming & Events 🔴
**Status**: NOT STARTED
**Target**: 1 week
**Dependencies**: Phase 1.4, Phase 3

#### Tasks:
- [ ] 4.1 StreamAdapter Enhancement
- [ ] 4.2 Event Consistency

### Phase 5: Reliability Layer 🔴
**Status**: NOT STARTED
**Target**: 1 week  
**Dependencies**: Phase 3.3

#### Tasks:
- [ ] 5.1 Error Type Verification
- [ ] 5.2 Retry Manager Testing

### Phase 6: Metrics & Documentation 🔴
**Status**: NOT STARTED
**Target**: 1 week
**Dependencies**: Phase 1-5

#### Tasks:
- [ ] 6.1 Metrics Implementation
- [ ] 6.2 Documentation Updates

### Phase 7: Testing & Validation 🔴
**Status**: NOT STARTED
**Target**: 1 week
**Dependencies**: Phase 1-6

#### Tasks:
- [ ] 7.1 Backward Compatibility Tests
- [ ] 7.2 Integration Tests

### Phase 8: Optional Adapters ⚪
**Status**: FUTURE
**Target**: 2-3 weeks
**Dependencies**: Phase 1-7 complete

#### Tasks:
- [ ] 8.1 OpenAI Agents SDK Adapter
- [ ] 8.2 Local/On-Prem Adapter Template

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
| Breaking API changes | High | Extensive backward compatibility testing |
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

## Current Status Summary

**⚠️ CRITICAL PATH**: Phase 0.5 (Directory Restructuring) must be completed before any other work can continue effectively.

### Why Restructuring is Critical:
1. Current structure doesn't match layered architecture
2. Normalization code is in wrong location (`llm/normalizers/` → `core/normalization/`)
3. Providers are buried deep (`llm/providers/` → `providers/`)
4. No clear layer separation makes it hard to enforce boundaries
5. Continuing without restructuring will require moving code multiple times

### Next Immediate Steps:
1. Review and approve RESTRUCTURING_PLAN.md
2. Create migration script for automated moves
3. Execute Phase 0.5 restructuring
4. Move completed Phase 1 work to correct locations
5. Continue Phase 1 in properly structured codebase
6. Use `PARALLEL_PLANNER.md` to assign parallel workstreams

### Work Completed (Needs Relocation):
- ProviderAdapter base class → Move to `providers/base.py`
- Usage normalization → Move to `core/normalization/usage.py`
- Parameter normalization → Move to `core/normalization/params.py`
- Updated GenerationParams → Keep in `models/generation.py`

---

Last Updated: 2025-08-13
Next Review: After Phase 0.5 completion