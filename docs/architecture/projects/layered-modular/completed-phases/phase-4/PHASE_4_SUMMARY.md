# Phase 4: Streaming & Events - Research Summary

## Research Findings

### Current Architecture Analysis

1. **Streaming Infrastructure**
   - ✅ StreamAdapter provides provider-specific normalization
   - ✅ All providers integrated with StreamAdapter
   - ✅ Basic metrics tracking (chunks, duration, throughput)
   - ✅ StreamingHelper provides collection patterns

2. **Event System**
   - ✅ EventManager with async callbacks
   - ✅ Typed event classes defined
   - ⚠️ Not integrated into client API
   - ⚠️ No filtering or transformation

3. **JSON Streaming Issues**
   - ❌ JSON post-processing heuristic in `SteerLLMClient.stream_with_usage`
   - ❌ Doesn't handle nested JSON or arrays of objects
   - ❌ No streaming validation
   - ❌ Potential for duplicate objects in OpenAI Responses API

4. **Usage Data Gaps**
   - ❌ xAI doesn't provide streaming usage (currently character-based estimation)
   - ❌ No token counting fallback with tiktoken
   - ❌ Inconsistent timing across providers
   - ❌ No confidence score for usage estimates

## Proposed Solutions

### 1. JsonStreamHandler
- Proper JSON parsing with depth tracking
- Handles nested objects and arrays of objects
- Streaming validation
- Repair strategies for incomplete JSON
- Opt-in feature via `enable_json_stream_handler` flag

### 2. UsageAggregator System
- Token counting with tiktoken (optional dependency)
- Character-based fallback when tiktoken unavailable
- Provider-specific implementations
- Accurate estimation within 5% with confidence scores
- Replace xAI's current character estimation

### 3. EventProcessor Pipeline
- Filtering by type, provider, predicate
- Event transformation (non-blocking)
- Batching for performance with rate limiting
- Correlation IDs for tracing
- Background processing to avoid blocking streams

### 4. Enhanced Client Integration
- Event callbacks in stream_with_usage
- Event processor support
- Backward compatible
- Opt-in features

## Implementation Plan

### Phase 4.1: StreamAdapter Enhancement (Days 1-2)
- JsonStreamHandler implementation
- Integration with StreamAdapter
- Provider-specific JSON handling
- Comprehensive testing

### Phase 4.2: Event Consistency (Days 3-5)
- EventProcessor pipeline
- Enhanced EventManager
- Client API integration
- Metrics hooks

### Testing Strategy
- Unit tests for all components
- Integration tests with providers
- Performance benchmarks
- Backward compatibility tests

## Key Benefits

1. **Reliability**
   - Robust JSON handling
   - Accurate usage tracking
   - No event loss

2. **Performance**
   - < 5ms JSON parsing
   - < 1ms event processing
   - Supports 1000+ events/sec

3. **Flexibility**
   - Configurable pipeline
   - Provider-specific handling
   - Extensible architecture

4. **Observability**
   - Streaming metrics
   - Event tracing
   - Performance monitoring

## Next Steps

1. Review technical design with team
2. Begin Day 1 implementation (JsonStreamHandler)
3. Set up performance benchmarks
4. Create integration test suite

## Files to Create/Modify

### New Files
- `streaming/json_handler.py` - JSON stream processing
- `streaming/aggregator.py` - Usage aggregation
- `streaming/processor.py` - Event processing pipeline

### Modified Files
- `streaming/adapter.py` - JSON awareness
- `streaming/manager.py` - Enhanced event manager
- `api/client.py` - Event integration with StreamingOptions
- `core/routing/router.py` - Enhanced streaming
- `providers/openai/streaming.py` - Existing, validate incremental deltas
- `providers/anthropic/streaming.py` - Existing, multi-content blocks
- `providers/xai/streaming.py` - Existing, usage aggregation integration

## Success Criteria

✅ All current tests remain green (233+), and new Phase 4 tests pass
✅ All JSON streaming tests pass with no duplicate objects
✅ No JSON duplication during streaming across OpenAI Responses API and Anthropic
✅ Usage accuracy within 5% with confidence scores
✅ Event processing < 1ms overhead (non-blocking)
✅ Backward compatibility maintained
✅ TTFT (Time To First Token) measured and exposed via metrics
✅ Documentation complete with examples

## Risks & Mitigations

1. **Performance** → Profile and optimize hot paths
2. **Compatibility** → Keep changes opt-in
3. **Complexity** → Clear documentation and examples
4. **Provider drift** → Isolated provider logic