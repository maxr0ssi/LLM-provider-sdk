"""Tests for JSON stream handler."""

import pytest
import json
from steer_llm_sdk.streaming.json_handler import JsonStreamHandler


class TestJsonStreamHandler:
    """Test JSON stream handler functionality."""
    
    def test_simple_object(self):
        """Test parsing a simple JSON object."""
        handler = JsonStreamHandler()
        
        # Single chunk
        result = handler.process_chunk('{"key": "value"}')
        assert result == {"key": "value"}
        
    def test_split_object(self):
        """Test parsing JSON split across chunks."""
        handler = JsonStreamHandler()
        
        # Split across chunks
        assert handler.process_chunk('{"key"') is None
        assert handler.process_chunk(': "val') is None
        result = handler.process_chunk('ue"}')
        assert result == {"key": "value"}
        
    def test_nested_object(self):
        """Test parsing nested JSON objects."""
        handler = JsonStreamHandler()
        
        nested = {
            "outer": {
                "inner": {
                    "value": 123
                }
            }
        }
        
        result = handler.process_chunk(json.dumps(nested))
        assert result == nested
        
    def test_array_handling(self):
        """Test parsing JSON arrays."""
        handler = JsonStreamHandler()
        
        # Simple array
        result = handler.process_chunk('[1, 2, 3]')
        assert result == [1, 2, 3]
        
        # Array of objects
        array = [{"id": 1}, {"id": 2}]
        result = handler.process_chunk(json.dumps(array))
        assert result == array
        
    def test_multiple_objects(self):
        """Test handling multiple JSON objects in stream."""
        handler = JsonStreamHandler()
        
        # Multiple objects in one chunk
        chunk = '{"first": 1}{"second": 2}'
        result1 = handler.process_chunk(chunk)
        # Should return the last complete object
        assert result1 == {"second": 2}
        
        # Check that both were captured
        stats = handler.get_statistics()
        assert stats["objects_found"] == 2
        
    def test_mixed_content(self):
        """Test handling JSON mixed with other content."""
        handler = JsonStreamHandler()
        
        # JSON with surrounding text
        chunk = 'Some text {"json": true} more text'
        result = handler.process_chunk(chunk)
        assert result == {"json": True}
        
    def test_escaped_strings(self):
        """Test handling escaped characters in strings."""
        handler = JsonStreamHandler()
        
        # Escaped quotes
        obj = {"key": "value with \"quotes\""}
        result = handler.process_chunk(json.dumps(obj))
        assert result == obj
        
        # Escaped backslashes
        obj = {"path": "C:\\Users\\test"}
        result = handler.process_chunk(json.dumps(obj))
        assert result == obj
        
    def test_unicode_handling(self):
        """Test handling Unicode characters."""
        handler = JsonStreamHandler()
        
        obj = {"text": "Hello 世界 🌍"}
        result = handler.process_chunk(json.dumps(obj))
        assert result == obj
        
    def test_incomplete_json_recovery(self):
        """Test recovery from incomplete JSON."""
        handler = JsonStreamHandler()
        
        # Add incomplete JSON
        handler.process_chunk('{"incomplete": "value"')
        
        # Get final object should attempt repair
        result = handler.get_final_object()
        assert result == {"incomplete": "value"}
        
    def test_complex_streaming_scenario(self):
        """Test realistic streaming scenario."""
        handler = JsonStreamHandler()
        
        # Simulate OpenAI-style streaming
        chunks = [
            '{"id": "chatcmpl-',
            '123", "object": "chat.completion.chunk",',
            ' "created": 1234567890, "model": "gpt-4", ',
            '"choices": [{"index": 0, "delta": {"content": "Hello"',
            '}, "finish_reason": null}]',
            '}'
        ]
        
        result = None
        for chunk in chunks:
            result = handler.process_chunk(chunk)
            
        assert result is not None
        assert result["id"] == "chatcmpl-123"
        assert result["choices"][0]["delta"]["content"] == "Hello"
        
    def test_array_streaming(self):
        """Test streaming arrays."""
        handler = JsonStreamHandler()
        
        # Stream array in chunks
        chunks = ['[{"id": 1', '}, {"id":', ' 2}]']
        
        result = None
        for chunk in chunks:
            result = handler.process_chunk(chunk)
            
        assert result == [{"id": 1}, {"id": 2}]
        
    def test_whitespace_handling(self):
        """Test handling of whitespace."""
        handler = JsonStreamHandler()
        
        # JSON with various whitespace
        chunk = '\n\t  {"key":\n\t"value"}\n\n'
        result = handler.process_chunk(chunk)
        assert result == {"key": "value"}
        
    def test_malformed_json(self):
        """Test handling of malformed JSON."""
        handler = JsonStreamHandler()
        
        # Malformed JSON should not crash
        handler.process_chunk('{"bad": "json"')
        handler.process_chunk('more bad stuff }}')
        
        # Should not have any complete objects
        stats = handler.get_statistics()
        assert stats["objects_found"] == 0
        
    def test_reset_functionality(self):
        """Test reset clears state."""
        handler = JsonStreamHandler()
        
        # Add some data
        handler.process_chunk('{"test": 1}')
        assert handler.get_statistics()["objects_found"] == 1
        
        # Reset
        handler.reset()
        stats = handler.get_statistics()
        assert stats["objects_found"] == 0
        assert stats["buffer_size"] == 0
        
    def test_get_final_object_precedence(self):
        """Test get_final_object returns last complete object."""
        handler = JsonStreamHandler()
        
        # Process multiple objects
        handler.process_chunk('{"first": 1}')
        handler.process_chunk('{"second": 2}')
        handler.process_chunk('{"third": 3}')
        
        # Should return the last one
        final = handler.get_final_object()
        assert final == {"third": 3}
        
    def test_bracket_matching(self):
        """Test proper bracket matching."""
        handler = JsonStreamHandler()
        
        # Nested with mixed brackets
        obj = {
            "array": [1, 2, {"nested": True}],
            "object": {"key": [3, 4, 5]}
        }
        
        result = handler.process_chunk(json.dumps(obj))
        assert result == obj
        
    def test_performance_large_object(self):
        """Test performance with large objects."""
        handler = JsonStreamHandler()
        
        # Create a large object
        large_obj = {
            f"key_{i}": {
                "data": list(range(100)),
                "nested": {"value": f"test_{i}"}
            }
            for i in range(100)
        }
        
        # Should handle large objects efficiently
        json_str = json.dumps(large_obj)
        result = handler.process_chunk(json_str)
        assert result == large_obj
        
    def test_streaming_with_responses_api_format(self):
        """Test handling Responses API JSON format."""
        handler = JsonStreamHandler()
        
        # Simulate Responses API streaming that might send complete objects
        chunks = [
            '{"text": "The"}',
            '{"text": "The answer"}',
            '{"text": "The answer is"}',
            '{"text": "The answer is 42"}'
        ]
        
        results = []
        for chunk in chunks:
            result = handler.process_chunk(chunk)
            if result:
                results.append(result)
                
        # Should have captured all objects
        assert len(results) == 4
        # Last should be complete
        assert results[-1] == {"text": "The answer is 42"}
        
        # Also test that all objects were stored
        all_objects = handler.get_all_objects()
        assert len(all_objects) == 4
        
    def test_repair_strategies(self):
        """Test JSON repair strategies."""
        handler = JsonStreamHandler()
        
        # Missing closing brace
        handler.buffer = '{"key": "value"'
        repaired = handler._repair_json(handler.buffer)
        assert repaired == {"key": "value"}
        
        # Missing closing bracket
        handler.buffer = '[1, 2, 3'
        repaired = handler._repair_json(handler.buffer)
        assert repaired == [1, 2, 3]
        
        # Nested unclosed
        handler.buffer = '{"outer": {"inner": "value"}'
        repaired = handler._repair_json(handler.buffer)
        assert repaired == {"outer": {"inner": "value"}}
        
    def test_empty_chunks(self):
        """Test handling empty chunks."""
        handler = JsonStreamHandler()
        
        # Empty chunks should not affect processing
        assert handler.process_chunk('') is None
        assert handler.process_chunk('{"key"') is None
        assert handler.process_chunk('') is None
        assert handler.process_chunk(': "value"}') == {"key": "value"}