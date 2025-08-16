# Streaming Architecture Consolidation Plan

> **Status**: ✅ IMPLEMENTED
> 
> This plan has been successfully implemented. See the [Streaming Architecture](streaming.md) documentation for the current architecture.

## Executive Summary

The current streaming architecture has evolved organically, resulting in three overlapping implementations that handle similar concerns differently. This plan outlines a comprehensive approach to consolidate these into a single, coherent streaming pipeline without backward-compatibility constraints (pre-release), improving maintainability and performance.

## Current State Analysis

### 1. Three Parallel Streaming Implementations

#### A. EventManager + Direct Emission (Low-Level)
- **Location**: `streaming/manager.py`
- **Usage**: AgentRunner, StreamingHelper
- **Characteristics**:
  - Direct event creation and emission
  - Manual event type handling
  - Factory methods for consistent metadata
  - Callback-based architecture

#### B. EventProcessor Pipeline (Mid-Level)
- **Location**: `streaming/processor.py`
- **Usage**: API client with JSON streaming
- **Characteristics**:
  - Filter/transform/batch pipeline
  - Background processing capability
  - Correlation and metrics enrichment
  - Factory function for configuration

#### C. StreamingHelper Orchestration (High-Level)
- **Location**: `streaming/helpers.py`
- **Usage**: Provider adapters, test utilities
- **Characteristics**:
  - High-level collect/stream patterns
  - Adapter integration
  - Built-in retry and error handling

### 2. Redundancy Analysis

#### Duplicate Event Handling Logic
```python
# Pattern 1: AgentRunner (manual)
async for item in self.router.generate_stream(...):
    if isinstance(item, tuple):
        chunk, usage_data = item
        if chunk is not None:
            await events.emit_delta(self.adapter.normalize_delta(chunk))
            collected.append(chunk)
        if usage_data is not None:
            final_usage = usage_data["usage"]
            await events.emit_usage(final_usage)

# Pattern 2: StreamingHelper (abstracted)
async for event in stream:
    delta = adapter.normalize_delta(event)
    if delta.text:
        chunks.append(delta.text)
        if events:
            await events.emit_delta(events.create_delta_event(...))

# Pattern 3: API Client (processor-based)
processor = create_event_processor(
    add_timestamp=True,
    background=True
)
# Events flow through processor pipeline
```

#### Duplicate Adapter Usage
- AgentRunner has its own StreamAdapter instance
- StreamingHelper requires adapter parameter
- EventProcessor doesn't use adapters directly

#### Inconsistent Error Handling
- AgentRunner: try/catch with emit_error
- StreamingHelper: try/finally with complete event
- EventProcessor: Silent error logging

### 3. Key Issues

1. **Code Duplication**: Same streaming loop logic in 3+ places
2. **Inconsistent Event Creation**: Some use factories, some don't
3. **Mixed Abstraction Levels**: Low-level emission mixed with high-level orchestration
4. **Adapter Integration**: Not uniformly applied across implementations
5. **Metrics/Observability**: Different approaches to tracking

## Proposed Unified Architecture (minimal, using existing building blocks)

### Design Principles

1. **Single Orchestration Path**: Use one high-level helper for all streaming patterns
2. **Keep Existing Primitives**: Reuse `StreamAdapter` and `EventProcessor`
3. **No Backwards Compatibility**: Remove legacy/manual paths (pre-release)
4. **Low Churn**: No new classes; remove duplicate loops
5. **Consistency**: Event emission and usage finalization handled in one place

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│   (AgentRunner, API Client, Provider Adapters)              │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                 StreamingHelper (orchestration)              │
│  (collect_with_usage, stream_with_events)                   │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                 EventProcessor (pipeline)                    │
│  (filters, transformers, batching, metrics)                 │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                 StreamAdapter (provider norm)                │
│  (delta normalization, JSON, usage aggregation, lifecycle)  │
└─────────────────────────────────────────────────────────────┘
```

### Core Components (as-implemented)

- **StreamAdapter**: Normalizes provider events, handles JSON mode, aggregates usage, and emits lifecycle events via `emit_event()` when an `EventProcessor` is attached with `set_event_processor(...)`.
- **EventProcessor**: Existing pipeline abstraction with filters/transformers/batching/metrics (kept as the single pipeline component).
- **StreamingHelper**: High-level patterns (`collect_with_usage`, `stream_with_events`) that orchestrate adapter and event flow. This becomes the only orchestration entry point used by `AgentRunner` and the API client.
- **EventManager**: Previously a typed-callback façade. Removed from internal orchestration; callbacks will be routed via `EventProcessor` only. Slated for removal before release.

## Implementation Plan (pre-release, no back-compat)

### Phase 1: Orchestration unification (Week 1)
- Replace manual loops in `AgentRunner` and API client with `StreamingHelper`:
  - AgentRunner → `StreamingHelper.stream_with_events(...)` + `StreamAdapter` lifecycle
  - API client → `StreamingHelper.collect_with_usage(...)` + `adapter.set_event_processor(...)`
- Remove direct uses of `EventManager` in core streaming paths.

Deliverables:
- Modified `agents/runner/agent_runner.py`
- Modified `api/client.py`

### Phase 2: Consistency + reliability hooks (Week 2)
- Replace `StreamAdapter._is_retryable_error` heuristic by delegating to error classifier/mapper.
- Keep streaming retry in router (`StreamingRetryManager`).

Deliverables:
- Modified `streaming/adapter.py`

### Phase 3: Cleanup and tests (Week 2–3)
- Remove remaining duplicate streaming loops and any dead code.
- Tests: chunk parity, single on_usage per provider, JSON dedup, TTFT metrics, error propagation.

Deliverables:
- Updated tests and docs

## Migration Strategy

### Backward Compatibility

1. **Maintain All Public APIs**
   ```python
   # Old API continues to work
   events = EventManager(on_delta=callback)
   
   # Internally uses new engine
   class EventManager(EventEngine):
       def __init__(self, on_start=None, on_delta=None, ...):
           # Convert callbacks to processors
           processors = [CallbackProcessor({
               'start': on_start,
               'delta': on_delta
           })]
           super().__init__(processors=processors)
   ```

2. **Gradual Deprecation**
   - Add deprecation warnings in Phase 3
   - Provide migration examples
   - Support old APIs for 2 major versions

3. **Feature Flags**
   ```python
   # Allow opting into new behavior
   os.environ['STEER_SDK_UNIFIED_STREAMING'] = 'true'
   ```

### Testing Strategy

1. **Parallel Testing**
   - Run same tests against old and new implementations
   - Ensure identical behavior
   - Performance regression tests

2. **Integration Tests**
   ```python
   @pytest.mark.parametrize("use_new_streaming", [False, True])
   async def test_streaming_behavior(use_new_streaming):
       # Test both implementations
   ```

3. **Migration Tests**
   - Test each migration step
   - Verify backward compatibility
   - Check deprecation warnings

## Benefits

### Immediate Benefits
1. **Reduced Code Duplication**: ~40% less streaming code
2. **Consistent Behavior**: All streaming follows same patterns
3. **Better Testing**: Single implementation to test
4. **Improved Debugging**: Centralized logging and metrics

### Long-term Benefits
1. **Easier Maintenance**: Single source of truth
2. **New Features**: Easy to add across all streaming
3. **Performance**: Optimizations benefit all code paths
4. **Extensibility**: Plugin architecture for processors

## Risks and Mitigation

### Risk 1: Breaking Changes
**Mitigation**: 
- Extensive backward compatibility layer
- Feature flags for gradual rollout
- Comprehensive test coverage

### Risk 2: Performance Regression
**Mitigation**:
- Benchmark before/after each phase
- Profile hot paths
- Optimization phase dedicated to performance

### Risk 3: Complex Migration
**Mitigation**:
- Phase approach allows gradual migration
- Each phase is independently valuable
- Can pause/rollback at phase boundaries

## Success Metrics

1. **Code Reduction**: 40% less streaming-related code
2. **Test Coverage**: 95%+ coverage of streaming paths
3. **Performance**: No regression, 10% improvement goal
4. **API Stability**: Zero breaking changes
5. **Developer Experience**: Simplified streaming APIs

## Conclusion

This consolidation plan addresses the identified redundancies in the streaming architecture while maintaining backward compatibility and improving the overall system design. The phased approach ensures we can deliver value incrementally while minimizing risk.

The unified architecture will make the SDK more maintainable, performant, and easier to extend with new streaming features. By consolidating around a single, well-designed streaming engine, we eliminate confusion about which pattern to use and ensure consistent behavior across all streaming scenarios.