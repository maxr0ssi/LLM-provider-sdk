"""Unit tests for EventManager factory methods with metadata enrichment."""

import re
import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from steer_llm_sdk.streaming.manager import EventManager
from steer_llm_sdk.models.events import (
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)


class TestEventManagerFactory:
    """Test EventManager factory methods."""
    
    def test_create_start_event_with_enrichment(self):
        """Test start event creation with metadata enrichment."""
        # Create EventManager with global metadata
        manager = EventManager(
            request_id="test-123",
            trace_id="trace-456",
            sdk_version="1.0.0"
        )
        
        # Create event
        event = manager.create_start_event(
            provider="openai",
            model="gpt-4"
        )
        
        # Verify enrichment
        assert event.provider == "openai"
        assert event.model == "gpt-4"
        assert event.request_id == "test-123"
        assert event.metadata["trace_id"] == "trace-456"
        assert event.metadata["sdk_version"] == "1.0.0"
        assert isinstance(event.timestamp, float)
        assert event.timestamp > 0
    
    def test_create_delta_event_with_enrichment(self):
        """Test delta event creation with metadata enrichment."""
        manager = EventManager(
            request_id="test-123",
            trace_id="trace-456"
        )
        
        # Create event
        event = manager.create_delta_event(
            delta="Hello world",
            chunk_index=0,
            provider="anthropic",
            model="claude-3"
        )
        
        # Verify enrichment
        assert event.delta == "Hello world"
        assert event.chunk_index == 0
        assert event.provider == "anthropic"
        assert event.request_id == "test-123"
        assert event.metadata["trace_id"] == "trace-456"
        assert "sdk_version" in event.metadata
    
    def test_create_usage_event_with_enrichment(self):
        """Test usage event creation with metadata enrichment."""
        manager = EventManager(request_id="test-123")
        
        usage = {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
        
        # Create event
        event = manager.create_usage_event(
            usage=usage,
            is_estimated=False,
            provider="openai"
        )
        
        # Verify enrichment
        assert event.usage == usage
        assert event.is_estimated is False
        assert event.request_id == "test-123"
        assert event.provider == "openai"
    
    def test_create_complete_event_with_enrichment(self):
        """Test complete event creation with metadata enrichment."""
        manager = EventManager(trace_id="trace-789")
        
        # Create event
        event = manager.create_complete_event(
            total_chunks=10,
            duration_ms=1500.5,
            provider="xai",
            model="grok"
        )
        
        # Verify enrichment
        assert event.total_chunks == 10
        assert event.duration_ms == 1500.5
        assert event.metadata["trace_id"] == "trace-789"
        assert event.provider == "xai"
        assert event.model == "grok"
    
    def test_create_error_event_with_enrichment(self):
        """Test error event creation with metadata enrichment."""
        manager = EventManager(request_id="error-123")
        
        error = ValueError("Test error")
        
        # Create event
        event = manager.create_error_event(
            error=error,
            error_type="ValueError",
            provider="openai",
            is_retryable=True
        )
        
        # Verify enrichment
        assert event.error == error
        assert event.error_type == "ValueError"
        assert event.request_id == "error-123"
        assert event.provider == "openai"
        assert event.is_retryable is True
    
    def test_custom_enrichment_hook(self):
        """Test custom enrichment hook."""
        def custom_enricher(event_type: str, kwargs: dict) -> dict:
            # Add custom metadata
            metadata = kwargs.setdefault("metadata", {})
            metadata["custom_field"] = f"enriched_{event_type}"
            metadata["environment"] = "test"
            return kwargs
        
        manager = EventManager(
            on_create_event=custom_enricher
        )
        
        # Create event
        event = manager.create_start_event(
            provider="openai",
            model="gpt-4"
        )
        
        # Verify custom enrichment
        assert event.metadata["custom_field"] == "enriched_start"
        assert event.metadata["environment"] == "test"
    
    def test_metrics_increment(self):
        """Test metrics increment when enabled."""
        manager = EventManager(metrics_enabled=True)
        
        # Mock the increment method
        manager._increment_metric = MagicMock()
        
        # Create various events
        manager.create_start_event("openai", "gpt-4")
        manager.create_delta_event("text", 0)
        manager.create_usage_event({"tokens": 10})
        manager.create_complete_event(5, 1000.0)
        manager.create_error_event(Exception(), "Exception")
        
        # Verify metrics were incremented
        assert manager._increment_metric.call_count == 5
        
        # Check specific calls
        calls = manager._increment_metric.call_args_list
        assert calls[0][0] == ('events.created',)
        assert calls[0][1] == {'tags': {'type': 'start'}}
        assert calls[1][1] == {'tags': {'type': 'delta'}}
        assert calls[2][1] == {'tags': {'type': 'usage'}}
        assert calls[3][1] == {'tags': {'type': 'complete'}}
        assert calls[4][1] == {'tags': {'type': 'error'}}
    
    def test_no_override_existing_fields(self):
        """Test that existing fields are not overridden."""
        manager = EventManager(
            request_id="manager-123",
            trace_id="manager-456"
        )
        
        # Create event with explicit values
        event = manager.create_start_event(
            provider="openai",
            model="gpt-4",
            request_id="event-999",  # Should not be overridden
            metadata={"trace_id": "event-888", "custom": "value"}  # Should merge
        )
        
        # Verify explicit values are preserved
        assert event.request_id == "event-999"
        assert event.metadata["trace_id"] == "event-888"  # Explicit value preserved
        assert event.metadata["custom"] == "value"  # Custom metadata preserved
        assert event.metadata["sdk_version"]  # Still has SDK version
    
    def test_timestamp_consistency(self):
        """Test that timestamp is set consistently."""
        manager = EventManager()
        
        start_time = time.time()
        event = manager.create_start_event("openai", "gpt-4")
        end_time = time.time()
        
        # Verify timestamp is within expected range
        assert start_time <= event.timestamp <= end_time
    
    def test_sdk_version_fallback(self):
        """Test SDK version fallback when not provided."""
        manager = EventManager()  # No explicit sdk_version
        
        event = manager.create_start_event("openai", "gpt-4")
        
        # Should have some SDK version (either real or "unknown")
        assert "sdk_version" in event.metadata
        version = event.metadata["sdk_version"]
        assert version == "unknown" or re.match(r"\d+\.\d+\.\d+", version)


@pytest.mark.asyncio
class TestEventManagerIntegration:
    """Integration tests for EventManager with callbacks."""
    
    async def test_factory_with_emit_integration(self):
        """Test that factory methods work with emit methods."""
        received_events = []
        
        async def on_start(event):
            received_events.append(event)
        
        manager = EventManager(
            on_start=on_start,
            request_id="test-123"
        )
        
        # Create and emit event
        event = manager.create_start_event("openai", "gpt-4")
        await manager.emit_start(event)
        
        # Verify event was received with enrichment
        assert len(received_events) == 1
        assert received_events[0].request_id == "test-123"
        assert received_events[0].provider == "openai"