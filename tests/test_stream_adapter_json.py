"""Tests for StreamAdapter JSON integration."""

import pytest
import json
from unittest.mock import MagicMock

from steer_llm_sdk.streaming.adapter import StreamAdapter
from steer_llm_sdk.streaming.types import StreamDelta


class TestStreamAdapterJSON:
    """Test StreamAdapter JSON handling functionality."""
    
    def test_json_handler_initialization(self):
        """Test JSON handler initialization."""
        adapter = StreamAdapter("openai")
        
        # Initially no JSON handler
        assert adapter.json_handler is None
        assert adapter.enable_json_handler is False
        
        # Enable JSON handler
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        
        assert adapter.json_handler is not None
        assert adapter.enable_json_handler is True
        assert adapter.response_format == {"type": "json_object"}
        
    def test_json_normalization(self):
        """Test JSON normalization in delta processing."""
        adapter = StreamAdapter("openai")
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        
        # Create mock OpenAI chunk with JSON text
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = '{"result": "success"}'
        
        # Process the chunk
        delta = adapter.normalize_delta(mock_chunk)
        
        # Should be detected as JSON
        assert delta.kind == "json"
        assert delta.value == {"result": "success"}
        assert delta.metadata["complete_json"] is True
        assert delta.metadata["json_handler"] is True
        
    def test_incremental_json_building(self):
        """Test incremental JSON building."""
        adapter = StreamAdapter("openai")
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        
        # Split JSON across multiple chunks
        chunks = ['{"key"', ': "val', 'ue"}']
        
        deltas = []
        for chunk_text in chunks:
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta.content = chunk_text
            
            delta = adapter.normalize_delta(mock_chunk)
            deltas.append(delta)
            
        # First two should be text
        assert deltas[0].kind == "text"
        assert deltas[1].kind == "text"
        
        # Last should be JSON
        assert deltas[2].kind == "json"
        assert deltas[2].value == {"key": "value"}
        
    def test_json_disabled_by_default(self):
        """Test that JSON handling is disabled by default."""
        adapter = StreamAdapter("openai")
        
        # Create mock chunk with JSON
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = '{"result": "success"}'
        
        # Process without enabling JSON handler
        delta = adapter.normalize_delta(mock_chunk)
        
        # Should remain as text
        assert delta.kind == "text"
        assert delta.value == '{"result": "success"}'
        
    def test_multiple_json_objects(self):
        """Test handling multiple JSON objects in stream."""
        adapter = StreamAdapter("anthropic")
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        
        # Simulate multiple complete JSON objects
        json_objects = [
            {"step": 1, "action": "init"},
            {"step": 2, "action": "process"},
            {"step": 3, "action": "complete"}
        ]
        
        found_json = []
        for obj in json_objects:
            mock_event = MagicMock()
            mock_event.type = "content_block_delta"
            mock_event.delta.text = json.dumps(obj)
            
            delta = adapter.normalize_delta(mock_event)
            if delta.kind == "json":
                found_json.append(delta.value)
                
        assert len(found_json) == 3
        assert found_json == json_objects
        
        # Check all objects are tracked
        all_objects = adapter.get_all_json_objects()
        assert len(all_objects) == 3
        
    def test_get_final_json(self):
        """Test getting final JSON object."""
        adapter = StreamAdapter("xai")
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        
        # Process multiple objects
        objects = [{"id": 1}, {"id": 2}, {"id": 3}]
        
        for obj in objects:
            mock_chunk = MagicMock()
            mock_chunk.content = json.dumps(obj)
            
            adapter.normalize_delta((None, mock_chunk))
            
        # Get final should return last object
        final = adapter.get_final_json()
        assert final == {"id": 3}
        
    def test_json_metrics(self):
        """Test JSON metrics in streaming metrics."""
        adapter = StreamAdapter("openai")
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        import asyncio
        asyncio.get_event_loop().run_until_complete(adapter.start_stream())
        
        # Process some JSON
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = '{"test": 1}'
        
        adapter.normalize_delta(mock_chunk)
        import asyncio
        asyncio.get_event_loop().run_until_complete(adapter.track_chunk(11))  # Track the chunk
        
        # Get metrics
        metrics = adapter.get_metrics()
        
        assert "json_objects_found" in metrics
        assert metrics["json_objects_found"] == 1
        assert "json_buffer_size" in metrics
        assert metrics["chunks"] == 1
        assert metrics["total_chars"] == 11
        
    def test_non_json_response_format(self):
        """Test that non-JSON response formats don't enable handler."""
        adapter = StreamAdapter("openai")
        
        # Set non-JSON response format
        adapter.set_response_format({"type": "text"}, enable_json_handler=True)
        
        # Handler should not be created
        assert adapter.json_handler is None
        
    def test_complex_json_streaming(self):
        """Test complex JSON streaming scenario."""
        adapter = StreamAdapter("openai")
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        
        # Simulate OpenAI Responses API style incremental JSON
        json_str = json.dumps({
            "reasoning": "Let me analyze this step by step",
            "steps": [
                {"number": 1, "action": "parse input"},
                {"number": 2, "action": "process data"},
                {"number": 3, "action": "generate output"}
            ],
            "result": {
                "success": True,
                "data": {"answer": 42}
            }
        })
        
        # Split into realistic chunks
        chunk_size = 20
        chunks = [json_str[i:i+chunk_size] for i in range(0, len(json_str), chunk_size)]
        
        json_found = False
        for chunk_text in chunks:
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta.content = chunk_text
            
            delta = adapter.normalize_delta(mock_chunk)
            if delta.kind == "json":
                json_found = True
                # Verify the complete object
                assert delta.value["reasoning"] == "Let me analyze this step by step"
                assert len(delta.value["steps"]) == 3
                assert delta.value["result"]["data"]["answer"] == 42
                break
                
        assert json_found, "Should have found complete JSON"
        
    def test_reset_json_handler(self):
        """Test resetting JSON handler state."""
        adapter = StreamAdapter("openai")
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        
        # Process some JSON
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = '{"first": 1}'
        adapter.normalize_delta(mock_chunk)
        
        assert len(adapter.get_all_json_objects()) == 1
        
        # Reset by setting new response format
        adapter.set_response_format({"type": "json_object"}, enable_json_handler=True)
        
        # Should have new handler
        assert len(adapter.get_all_json_objects()) == 0