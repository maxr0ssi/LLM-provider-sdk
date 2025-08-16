# Repository Cleanup & Audit Report - Verified (Pre-Release)

This verified report lists actual redundancies, inefficiencies, and recommended edits based on current codebase state.

## Executive summary

- Agents runtime: OpenAI Agents SDK only, no fallback (correctly documented)
- Pricing: Successfully moved to `ModelConfig`, no constants imports remain
- Cost computation: Properly centralized in selector.py
- Remaining issues: JSON parsing duplication, error class duplication

## High-priority items (P0) - VERIFIED

### 1) ✅ COMPLETED - Single-source pricing
- **Status**: Already implemented correctly
- **Evidence**: No imports of constants in selector.py or router.py
- **Note**: Pricing migration to ModelConfig is complete

### 2) ❌ INCORRECT - No mapping duplication found
- **Status**: Functions exist only in `integrations/agents/mapping.py`
- **Evidence**: `prepare_schema_for_responses_api` and `map_token_limit_param` are not duplicated

### 3) ✅ CONFIRMED - Normalize streaming JSON/event handling
- **Files**: `streaming/adapter.py`, `integrations/agents/streaming.py`, `api/client.py`
- **Problem**: client.py re-parses JSON after streaming adapters (lines 270-284)
- **Action**: Remove JSON re-parsing in client.py; trust adapter's JSON handling

### 4) ✅ CONFIRMED - Docs correctly state "no fallback"
- **Files**: `docs/integrations/openai-agents/overview.md`, `technical-design.md`
- **Status**: Properly documented with "no fallback paths" and "Agent runs must use the OpenAI Agents SDK"

## Important items (P1) - VERIFIED

### 5) ✅ CONFIRMED - Cost computation IS centralized
- **Status**: Only `selector.py` defines cost functions
- **Evidence**: Only router.py and agents adapter import and use `calculate_exact_cost`
- **No action needed**

### 6) ✅ CONFIRMED - Error class duplication exists
- **Files**: `integrations/agents/errors.py`, `reliability/errors.py`
- **Problem**: Both define `ProviderError` and `SchemaError`
- **Action**: Consolidate to use base errors from one location

### 7) ✅ PARTIALLY CORRECT - OpenAI adapter is large but organized
- **Files**: `providers/openai/adapter.py` (535 lines)
- **Status**: Already delegates to `payloads.py`, `parsers.py`, `streaming.py`
- **Action**: Could be further modularized but not critical

### 8) ✅ CONFIRMED - StreamingOptions properly handled
- **Status**: Router correctly respects StreamingOptions when provided
- **Evidence**: Lines 247-254 in router.py use StreamingOptions values
- **No action needed**

### 9) ✅ CONFIRMED - Tool schema handling is centralized
- **Files**: `integrations/agents/openai/tools.py`
- **Status**: All tool-to-SDK conversion happens in tools.py
- **No action needed**

## Medium items (P2) - Not Verified

These items were not verified in this audit:
- EventManager usage consistency
- Packaging footprint
- README/API reference drift

## Completed in pricing migration

- ✅ All models have exact pricing in ModelConfig
- ✅ Pricing validation ensures both input/output costs are set
- ✅ Constants.py converted to metadata only
- ✅ Pricing override system implemented (internal-only after security review)
- ✅ All tests updated and passing

## Concrete action items

### Must Fix (P0):
1. **JSON parsing duplication in client.py**
   - [ ] Remove lines 270-284 in `api/client.py` that re-parse JSON
   - [ ] Trust the streaming adapter's JSON handler completely

### Should Fix (P1):
2. **Error class duplication**
   - [ ] Remove duplicate classes from `reliability/errors.py`
   - [ ] Use base errors from `integrations/agents/errors.py` or vice versa
   - [ ] Update all imports accordingly

### Consider (P2):
3. **OpenAI adapter modularization**
   - [ ] Consider splitting adapter further if it grows beyond 600 lines
   - [ ] Current delegation pattern is acceptable

## Summary

The codebase is in better shape than the original audit suggested:
- Pricing migration is complete
- Cost computation is properly centralized  
- StreamingOptions are correctly handled
- Tool schema handling is centralized
- Agent documentation correctly states "no fallback"

Only two significant issues remain:
1. JSON re-parsing in client.py (high priority)
2. Error class duplication (medium priority)

## References

- Pricing sources: config/models.py (single source of truth)
- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/