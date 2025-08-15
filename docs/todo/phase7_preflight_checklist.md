# Phase 7 Preflight Checklist and Technical To‑Dos

This document consolidates a deep repo review of implementation status and critical issues to address before the Phase 7 upgrade.

**Last Updated**: 2025-08-15 (Post Phase 6 completion)

## Executive Summary

- Phases 0–6: **COMPLETE** and integrated
- Metrics infrastructure: **IMPLEMENTED** with tracking in client.py
- Streaming await calls: **FIXED** across all providers
- Before Phase 7: Only 3 minor fixes needed (StreamingOptions duplicates, router config, request_id)

---

## Must‑Do (True Blockers for Phase 7)

### 1. ❌ Deduplicate `StreamingOptions` reliability fields
- **File**: `steer_llm_sdk/models/streaming.py`
- **Issue**: `connection_timeout`, `read_timeout`, `retry_on_connection_error`, `max_reconnect_attempts` are declared twice (lines 76-102)
- **Action**: Remove duplicate declarations, keep only one set

### 2. ❌ Router streaming retry must derive from `StreamingOptions`
- **File**: `steer_llm_sdk/core/routing/router.py`
- **Issue**: `StreamingRetryConfig` uses hardcoded defaults (lines 252-258)
- **Action**: If `streaming_options` present in params, build `StreamingRetryConfig` from those values

### 3. ❌ Unify `request_id` propagation
- **Files**: `core/routing/router.py`, provider adapters
- **Issue**: Router generates `request_id` but providers generate their own
- **Action**: Pass router's `request_id` to `ProviderLogger.track_request(request_id=...)`

---

## Already Completed (No Action Needed)

### ✅ Metrics wiring at request boundaries
- **Status**: COMPLETE
- **Evidence**: Client.py has `track_request` context managers in:
  - `generate()` method (lines 109-123)
  - `stream_with_usage()` method (lines 226-257)
- **Metrics tracked**: duration_ms, TTFT, tokens, provider, model

### ✅ Provider await calls in streaming
- **Status**: COMPLETE
- **Evidence**: All providers properly await:
  - OpenAI: `await adapter.start_stream()`, `await adapter.track_chunk()`, `await adapter.complete_stream()`
  - Anthropic: All calls awaited (just fixed in Phase 6)
  - xAI: All calls awaited

### ✅ Short-circuit retry on explicit provider signal
- **Status**: COMPLETE
- **Evidence**: `reliability/enhanced_retry.py` lines 247-249
- **Implementation**: Early return when `ProviderError.is_retryable=True`

### ✅ Expanded error classification patterns
- **Status**: COMPLETE
- **Evidence**: `reliability/error_classifier.py`
- **Patterns**: Expanded from 5 to 13 rate limit patterns

### ✅ StreamingRetryManager state TTL configuration
- **Status**: COMPLETE
- **Evidence**: Configurable via `STEER_STREAMING_STATE_TTL` environment variable
- **Default**: 900 seconds (15 minutes)

---

## Non-Issues (Misunderstood or Non-existent)

### ⚠️ JSON fallback heuristic
- **Status**: NOT FOUND
- **Note**: The "last object" heuristic mentioned doesn't exist in current code
- **Action**: None needed

### ⚠️ Circuit breaker performance
- **Status**: PREMATURE OPTIMIZATION
- **Note**: Current implementation is fine; no evidence of lock contention
- **Action**: None needed unless performance issues observed

---

## Nice-to-Have Enhancements (Post Phase 7)

### 📋 Documentation Updates
- [ ] Update `PHASE_TRACKER.md` to mark Phase 6 as COMPLETE
- [ ] Add "Enable Metrics" section in README with example
- [ ] Document StreamingOptions configuration in guides

### 🔧 Configuration Improvements
- [ ] Add performance profile presets (HIGH_THROUGHPUT, JSON_MODE, DEBUG)
- [ ] Document retry/timeout behavior more clearly
- [ ] Add example configurations for common use cases

### 🧪 Test Enhancements
- [ ] Add E2E metrics validation test
- [ ] Add router reliability metrics test
- [ ] Relax aggregator accuracy tests for edge cases (emoji, short text)

---

## Exit Criteria for Phase 7 Start

1. ✅ **Metrics tracking**: COMPLETE - Client tracks all requests
2. ✅ **Streaming await calls**: COMPLETE - All providers properly await
3. ✅ **Error classification**: COMPLETE - 13 patterns, retryable logic
4. ✅ **Streaming state TTL**: COMPLETE - Configurable via env
5. ❌ **StreamingOptions deduplication**: PENDING - Remove duplicates
6. ❌ **Router streaming config**: PENDING - Use StreamingOptions
7. ❌ **Request ID propagation**: PENDING - Pass through to providers

**Ready for Phase 7**: After fixing the 3 pending items (estimated: 1 hour)

---

## Summary

The original checklist was created before Phase 5-6 completion and is significantly outdated:
- **70% of "must-do" items are already complete**
- **Only 3 real issues remain** (all minor)
- **No major architectural problems**
- **Metrics and reliability layers are fully functional**

The codebase is in much better shape than the original checklist suggests. Phase 7 can begin after a quick cleanup of the 3 remaining issues.