"""Unit tests for AgentStreamingBridge."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any

from steer_llm_sdk.integrations.agents.streaming import AgentStreamingBridge
from steer_llm_sdk.streaming.manager import EventManager
from steer_llm_sdk.models.events import (
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)


class TestAgentStreamingBridge:
    """Test AgentStreamingBridge functionality."""
    
    @pytest.fixture
    def mock_event_manager(self):
        """Create mock EventManager."""
        manager = Mock(spec=EventManager)
        manager.emit_event = AsyncMock()
        return manager
    
    @pytest.fixture
    def bridge(self, mock_event_manager):
        """Create bridge instance."""
        return AgentStreamingBridge(
            events=mock_event_manager,
            provider="openai",
            model="gpt-4o-mini",
            request_id="test-123"
        )
    
    @pytest.mark.asyncio
    async def test_on_start(self, bridge, mock_event_manager):
        """Test stream start event."""
        await bridge.on_start({"test": "metadata"})
        
        # Verify event emitted
        assert mock_event_manager.emit_event.called
        event = mock_event_manager.emit_event.call_args[0][0]
        assert isinstance(event, StreamStartEvent)
        assert event.provider == "openai"
        assert event.model == "gpt-4o-mini"
        assert event.request_id == "test-123"
    
    @pytest.mark.asyncio
    async def test_on_delta_text(self, bridge, mock_event_manager):
        """Test stream delta with text."""
        await bridge.on_delta("Hello world")
        
        # Verify text collected
        assert bridge._collected_text == ["Hello world"]
        assert bridge._chunk_count == 1
        
        # Verify event emitted
        event = mock_event_manager.emit_event.call_args[0][0]
        assert isinstance(event, StreamDeltaEvent)
        assert event.delta == "Hello world"
        assert event.chunk_index == 1
    
    @pytest.mark.asyncio
    async def test_on_usage(self, bridge, mock_event_manager):
        """Test usage event."""
        usage = {"prompt_tokens": 10, "completion_tokens": 20}
        await bridge.on_usage(usage, is_estimated=False)
        
        # Verify usage stored
        assert bridge._final_usage == usage
        assert bridge._usage_emitted is True
        
        # Verify event emitted
        event = mock_event_manager.emit_event.call_args[0][0]
        assert isinstance(event, StreamUsageEvent)
        assert event.usage == usage
        assert event.is_estimated is False
    
    @pytest.mark.asyncio
    async def test_get_collected_text(self, bridge):
        """Test text collection."""
        await bridge.on_delta("Hello ")
        await bridge.on_delta("world")
        await bridge.on_delta("!")
        
        assert bridge.get_collected_text() == "Hello world!"
    
    @pytest.mark.asyncio
    async def test_get_final_usage(self, bridge):
        """Test usage retrieval."""
        # No usage yet
        assert bridge.get_final_usage() is None
        
        # After usage event
        usage = {"prompt_tokens": 10, "completion_tokens": 20}
        await bridge.on_usage(usage)
        
        assert bridge.get_final_usage() == usage
    
    @pytest.mark.asyncio
    async def test_response_format_json_handler(self, mock_event_manager):
        """Test JSON handler configuration."""
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "test",
                "schema": {"type": "object"}
            }
        }
        
        bridge = AgentStreamingBridge(
            events=mock_event_manager,
            provider="openai",
            model="gpt-4o-mini",
            response_format=response_format
        )
        
        # Verify response format stored
        assert bridge.response_format == response_format
        # Note: json_handler is only created when set_response_format is called
        # The bridge calls it conditionally based on response_format type
    
    @pytest.mark.asyncio
    async def test_on_complete(self, bridge, mock_event_manager):
        """Test stream completion."""
        # Add some chunks first
        await bridge.on_delta("Test ")
        await bridge.on_delta("complete")
        
        await bridge.on_complete({"final": "metadata"})
        
        # Verify event emitted
        event = mock_event_manager.emit_event.call_args[0][0]
        assert isinstance(event, StreamCompleteEvent)
        assert event.total_chunks == 2
        assert event.duration_ms > 0
    
    @pytest.mark.asyncio
    async def test_on_error(self, bridge, mock_event_manager):
        """Test error handling."""
        error = Exception("Test error")
        await bridge.on_error(error)
        
        # Verify event emitted
        event = mock_event_manager.emit_event.call_args[0][0]
        assert isinstance(event, StreamErrorEvent)
        assert event.error == error
        assert event.error_type == "Exception"
        assert event.is_retryable is False
    
    @pytest.mark.asyncio
    async def test_on_error_retryable(self, bridge, mock_event_manager):
        """Test retryable error detection."""
        error = Exception("Connection timeout")
        await bridge.on_error(error)
        
        event = mock_event_manager.emit_event.call_args[0][0]
        assert event.is_retryable is True  # timeout is retryable