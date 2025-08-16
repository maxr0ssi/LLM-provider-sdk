# EventManager Usage Audit Report

## Summary

The EventManager is used consistently for emitting events, but event creation is scattered across multiple files with direct instantiation of event classes.

## Current State

### Event Creation Patterns Found

1. **Direct instantiation in streaming/helpers.py** (10 instances)
   ```python
   await events.emit_start(StreamStartEvent(
       provider=adapter.provider,
       model=adapter.model,
       ...
   ))
   ```

2. **Direct instantiation in integrations/agents/streaming.py** (5 instances)
   ```python
   event = StreamStartEvent(
       provider=self.provider,
       model=self.model,
       ...
   )
   ```

3. **Direct instantiation in streaming/adapter.py** (5 instances)
   ```python
   await self.emit_event(StreamStartEvent(
       stream_id=self._request_id
   ))
   ```

### Issues Identified

1. **No centralized event creation** - Events are created directly, bypassing any potential metrics or validation
2. **Inconsistent metadata** - Different files may include different metadata fields
3. **No opportunity for event enhancement** - Can't easily add global metadata or metrics

## Improvements Made

### Added Factory Methods to EventManager

```python
class EventManager:
    # Factory methods for consistent event creation
    def create_start_event(self, provider: str, model: str, **kwargs) -> StreamStartEvent
    def create_delta_event(self, delta: Any, chunk_index: int, **kwargs) -> StreamDeltaEvent
    def create_usage_event(self, usage: Dict[str, Any], is_estimated: bool = False, **kwargs) -> StreamUsageEvent
    def create_complete_event(self, total_chunks: int, duration_ms: float, **kwargs) -> StreamCompleteEvent
    def create_error_event(self, error: Exception, error_type: str, **kwargs) -> StreamErrorEvent
```

## Recommended Next Steps

### 1. Update Direct Event Creation (20 files to update)

Replace all direct instantiation with factory methods:

```python
# Before
await events.emit_start(StreamStartEvent(provider=provider, model=model))

# After
event = events.create_start_event(provider=provider, model=model)
await events.emit_start(event)

# Or combined
await events.emit_start(
    events.create_start_event(provider=provider, model=model)
)
```

### 2. Benefits of Factory Methods

- **Metrics**: Can add metrics/telemetry in one place
- **Validation**: Can validate event data before creation
- **Enrichment**: Can add global metadata (request_id, timestamp, etc.)
- **Evolution**: Easy to add new fields without updating all call sites

### 3. Future Enhancements

```python
def create_start_event(self, provider: str, model: str, **kwargs) -> StreamStartEvent:
    """Create a start event with consistent metadata."""
    # Future: Add global metadata
    kwargs['timestamp'] = time.time()
    kwargs['sdk_version'] = SDK_VERSION
    
    # Future: Emit metrics
    self.metrics.increment('events.created', tags={'type': 'start'})
    
    # Future: Validate required fields
    self._validate_provider(provider)
    
    return StreamStartEvent(provider=provider, model=model, **kwargs)
```

## Impact Assessment

- **Risk**: Low - Factory methods are additive, don't break existing code
- **Effort**: Medium - Need to update ~20 call sites across 3 files
- **Benefit**: High - Better observability, easier evolution, consistent events

## Conclusion

The EventManager is well-designed for event emission but lacks centralized event creation. The added factory methods provide a foundation for consistent event creation, but the existing direct instantiations should be updated to use these methods for maximum benefit.

This is a low-priority improvement that would enhance code quality and maintainability without affecting functionality.