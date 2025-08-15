# Phase 4: Streaming & Events - Implementation Plan

## Overview
Phase 4 focuses on enhancing the streaming infrastructure to provide consistent, reliable streaming across all providers with proper event emission and usage finalization.

## Current State Analysis

### What's Already Working Well
1. **StreamAdapter** (`streaming/adapter.py`)
   - Provider-specific delta normalization (OpenAI, Anthropic, xAI)
   - Streaming metrics tracking (chunks, duration, throughput)
   - Usage extraction from provider events
   - Should-emit-usage detection logic

2. **StreamDelta** (`streaming/types.py`)
   - Normalized delta structure with text/json kinds
   - Provider metadata preservation
   - Text extraction helper method

3. **StreamingHelper** (`streaming/helpers.py`)
   - `collect_with_usage()` - Collects all chunks with usage and metrics
   - `stream_with_events()` - Streams with EventManager integration
   - Error handling with event emission

4. **EventManager** (`streaming/manager.py`)
   - Async event callbacks (on_start, on_delta, on_usage, on_complete, on_error)
   - Typed event classes (StreamStartEvent, StreamDeltaEvent, etc.)

5. **Provider Integration**
   - All providers use StreamAdapter for normalization
   - Consistent streaming patterns across providers
   - Usage data properly extracted and normalized

### Identified Gaps

1. **JSON vs Text Streaming**
   - No explicit handling of JSON response format streaming
   - Potential for duplicate JSON objects in stream (mentioned in tracker)
   - Need normalization for structured output streaming

2. **End-of-Stream Usage Finalization**
   - Usage data timing varies by provider
   - Some providers don't provide usage in streaming
   - Need consistent finalization pattern

3. **Event System Enhancement**
   - Event callbacks not fully integrated into client API
   - Missing provider-specific event metadata
   - No event filtering/transformation capabilities

4. **Streaming Reliability**
   - Limited retry support for streaming connections
   - No automatic reconnection for interrupted streams
   - Missing backpressure handling

5. **Metrics and Observability**
   - Streaming metrics not integrated with observability layer
   - No streaming-specific performance tracking
   - Missing latency measurements for first token

## Implementation Tasks

### 4.1 StreamAdapter Enhancement

#### 4.1.1 JSON Response Format Handling
- Add `response_format` awareness to StreamAdapter
- Implement JSON object deduplication for streaming
- Handle partial JSON chunks and reassembly
- Add JSON validation during streaming

#### 4.1.2 Provider-Specific Enhancements
- **OpenAI**: Handle Responses API JSON streaming peculiarities, validate incremental deltas (existing `providers/openai/streaming.py`)
- **Anthropic**: Improve content block type detection for multi-content blocks (existing `providers/anthropic/streaming.py`)
- **xAI**: Replace character estimation with UsageAggregator token counting (existing `providers/xai/streaming.py`)

#### 4.1.3 Usage Finalization Patterns
- Create `UsageAggregator` class for providers without streaming usage
- Implement token counting fallback
- Add usage estimation based on chunk counts
- Ensure consistent usage shape across all providers

### 4.2 Event Consistency

#### 4.2.1 Enhanced Event System
- Create `StreamEventProcessor` for event transformation
- Add event filtering capabilities
- Implement event batching for high-frequency streams
- Add event replay for debugging

#### 4.2.2 Uniform Event Emission
- Standardize event emission timing across providers
- Add provider-specific metadata to events
- Implement guaranteed event ordering
- Add event correlation IDs

#### 4.2.3 Metrics Integration
- Connect streaming events to MetricsSink
- Add streaming-specific metrics:
  - Time to first token (TTFT)
  - Inter-token latency
  - Stream duration
  - Token throughput
- Create streaming dashboards

## Detailed Work Breakdown

### Day 1-2: JSON Streaming Enhancement
1. **Morning**: Analyze JSON streaming issues
   - Review test failures and edge cases
   - Document JSON streaming behavior per provider
   - Design deduplication algorithm

2. **Afternoon**: Implement JSON handling
   - Update StreamAdapter with JSON awareness
   - Add `JsonStreamProcessor` for partial JSON handling
   - Implement deduplication logic
   - Add comprehensive tests

3. **Day 2**: Provider-specific fixes
   - Fix OpenAI Responses API JSON streaming
   - Update Anthropic content block handling
   - Add JSON validation during streaming

### Day 3-4: Usage Finalization
1. **Morning**: Design usage aggregation
   - Create `UsageAggregator` interface
   - Design token counting strategy
   - Plan provider-specific implementations

2. **Afternoon**: Implement aggregation
   - Create base `UsageAggregator` class
   - Implement provider-specific aggregators
   - Add token estimation logic
   - Integrate with StreamAdapter

3. **Day 4**: Testing and validation
   - Test usage accuracy across providers
   - Validate token counting
   - Add usage comparison tests

### Day 5: Event System Enhancement
1. **Morning**: Event processor design
   - Design `StreamEventProcessor` interface
   - Plan event transformation pipeline
   - Design filtering system

2. **Afternoon**: Implementation
   - Implement event processor
   - Add event filtering
   - Create event transformers
   - Add correlation IDs

3. **Evening**: Integration
   - Wire event processor into streaming
   - Update all providers
   - Add configuration options

### Day 6-7: Testing and Documentation
1. **Day 6**: Comprehensive testing
   - Unit tests for all new components
   - Integration tests for streaming scenarios
   - Performance tests for event system
   - Edge case testing

2. **Day 7**: Documentation and polish
   - Update streaming documentation
   - Create event system guide
   - Add code examples
   - Performance optimization

## File Structure

```
steer_llm_sdk/
├── streaming/
│   ├── adapter.py          # Enhanced with JSON handling
│   ├── types.py            # Extended event types
│   ├── helpers.py          # Additional helpers
│   ├── manager.py          # Enhanced EventManager
│   ├── processor.py        # NEW: Event processor
│   ├── aggregator.py       # NEW: Usage aggregator
│   └── json_handler.py     # NEW: JSON stream handling
```

## Success Criteria

1. **JSON Streaming**
   - ✅ No duplicate JSON objects in streams
   - ✅ Proper handling of partial JSON chunks
   - ✅ Validation during streaming
   - ✅ All JSON tests passing

2. **Usage Finalization**
   - ✅ Consistent usage data shape across providers
   - ✅ Accurate token counting when not provided
   - ✅ Usage available for all streaming responses
   - ✅ No missing usage data

3. **Event System**
   - ✅ All providers emit consistent events
   - ✅ Event timing is predictable
   - ✅ Metrics integration working
   - ✅ No event loss or duplication

4. **Performance**
   - ✅ No streaming latency regression
   - ✅ Memory usage remains bounded
   - ✅ Event processing < 1ms overhead
   - ✅ Scales to 1000+ chunks/second

## Risk Mitigation

1. **Provider API Changes**
   - Keep provider-specific logic isolated
   - Comprehensive test coverage
   - Version pinning in tests

2. **Performance Impact**
   - Benchmark before/after
   - Profile event processing
   - Optimize hot paths

3. **Backward Compatibility**
   - Keep existing APIs unchanged
   - Add new features as opt-in
   - Comprehensive compatibility tests

## Dependencies

- Phase 3 completion (✅ DONE)
- All provider adapters working
- StreamAdapter infrastructure in place
- Basic EventManager functionality

## Next Steps

After Phase 4 completion:
1. Phase 5: Reliability Layer - Enhanced retry mechanisms
2. Phase 6: Metrics & Documentation - Full observability
3. Phase 7: Optional Adapters - Native SDK support