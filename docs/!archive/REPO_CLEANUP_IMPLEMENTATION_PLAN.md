# Repository Cleanup Implementation Plan

Based on the verified audit report, this plan addresses the actual issues found in the codebase.

## Phase 1: Critical Issues (P0) - 1-2 hours

### 1.1 Fix JSON Re-parsing in client.py
**Issue**: Client re-parses JSON after streaming adapters already handle it
**Impact**: Potential data corruption, performance overhead, conflicting parsing logic

**Implementation**:
1. Remove JSON post-processing block (lines 262-284) in `api/client.py`
2. Update `StreamResponseWrapper` to use adapter's JSON directly:
   - Add method to get JSON from underlying adapter
   - Remove heuristic JSON extraction logic
3. Ensure `response_wrapper.get_json()` returns adapter's parsed JSON
4. Update tests to verify JSON handler results are preserved

**Files to modify**:
- `steer_llm_sdk/api/client.py`
- `steer_llm_sdk/models/streaming.py` (StreamResponseWrapper)
- `tests/unit/test_streaming_json.py` (if exists)

## Phase 2: Important Issues (P1) - 2-3 hours

### 2.1 Consolidate Error Classes
**Issue**: Duplicate ProviderError and SchemaError in two modules
**Impact**: Confusion about which errors to use, potential import conflicts

**Implementation**:
1. Decide on single source of truth:
   - Option A: Use `steer_llm_sdk/providers/errors.py` as base (recommended)
   - Option B: Use `reliability/errors.py` as base
2. Update duplicate module to import from base:
   ```python
   # In integrations/agents/errors.py
   from ....providers.errors import ProviderError as BaseProviderError
   from ....providers.errors import SchemaError as BaseSchemaError
   
   # Alias for backward compatibility if needed
   ProviderError = BaseProviderError
   SchemaError = BaseSchemaError
   ```
3. Add agent-specific errors only in agents module
4. Update all imports across codebase
5. Run tests to ensure no breakage

**Files to modify**:
- `steer_llm_sdk/integrations/agents/errors.py`
- `steer_llm_sdk/reliability/errors.py`
- Any files importing these errors

### 2.2 Review OpenAI Adapter Modularization
**Issue**: Adapter is 535 lines (not critical but could be cleaner)
**Impact**: Maintainability

**Implementation**:
1. Analyze adapter for logical sections
2. Consider extracting:
   - Parameter validation logic → `validators.py`
   - Response building logic → `responses.py`
   - Error handling logic → use centralized errors
3. Keep core flow in adapter, delegate specifics

**Files to modify**:
- `steer_llm_sdk/providers/openai/adapter.py`
- Create new modules as needed

## Phase 3: Medium Priority (P2) - 2-3 hours

### 3.1 EventManager Usage Audit
**Implementation**:
1. Search for direct event construction outside EventManager
2. Replace with EventManager methods
3. Document EventManager as the sole event factory

### 3.2 Packaging Footprint Review
**Implementation**:
1. Review MANIFEST.in
2. Add exclusions for:
   - `tests/`
   - `docs/`
   - `examples/`
   - `*.md` files (except README.md)
3. Test sdist/wheel size reduction

### 3.3 README/API Reference Update
**Implementation**:
1. Ensure all examples use new streaming API:
   - `stream()` returns async generator
   - `stream_with_usage()` returns awaitable
2. Remove any references to `return_usage` parameter
3. Update migration guide

## Execution Order

1. **Day 1**: Phase 1 (Critical JSON parsing fix)
   - High impact, relatively simple fix
   - Prevents potential data corruption

2. **Day 2**: Phase 2.1 (Error consolidation)
   - Medium complexity, improves code organization
   - Sets foundation for better error handling

3. **Day 3**: Phase 2.2 + Phase 3
   - Lower priority improvements
   - Can be done incrementally

## Testing Strategy

### After Phase 1:
- Test streaming with JSON response format
- Verify adapter's JSON is preserved
- Check no double parsing occurs

### After Phase 2.1:
- Run full test suite
- Check all error imports resolve correctly
- Verify error inheritance chain

### After Phase 2.2:
- Ensure OpenAI adapter tests pass
- Benchmark performance (should be same or better)

### After Phase 3:
- Test package build
- Verify examples in README work
- Check documentation accuracy

## Risk Mitigation

1. **JSON Parsing Changes**:
   - Risk: Breaking existing JSON streaming behavior
   - Mitigation: Comprehensive streaming tests before/after

2. **Error Class Changes**:
   - Risk: Breaking imports in user code
   - Mitigation: Keep aliases for backward compatibility

3. **Adapter Refactoring**:
   - Risk: Introducing bugs in critical path
   - Mitigation: Extensive testing, incremental changes

## Success Metrics

- ✅ No JSON re-parsing in streaming path
- ✅ Single source of truth for each error class
- ✅ All tests passing
- ✅ No performance regression
- ✅ Cleaner, more maintainable code structure

## Notes

- Skip pricing-related items (already completed)
- Skip mapping duplication (doesn't exist)
- Skip StreamingOptions issues (working correctly)
- Focus on real, verified issues only