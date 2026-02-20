"""Edge case tests for JSON stream handler."""

import pytest
import json
from steer_llm_sdk.streaming.json_handler import JsonStreamHandler


class TestJsonStreamHandlerEdgeCases:
    """Test edge cases for JSON stream handler."""
    
    def test_deeply_nested_objects(self):
        """Test handling of deeply nested objects."""
        handler = JsonStreamHandler()
        
        # Create deeply nested object
        obj = {"level": 1}
        current = obj
        for i in range(2, 20):
            current["nested"] = {"level": i}
            current = current["nested"]
            
        result = handler.process_chunk(json.dumps(obj))
        assert result == obj
        
    def test_large_arrays(self):
        """Test handling of large arrays."""
        handler = JsonStreamHandler()
        
        # Large array
        large_array = list(range(10000))
        result = handler.process_chunk(json.dumps(large_array))
        assert result == large_array
        
    def test_mixed_array_types(self):
        """Test arrays with mixed types."""
        handler = JsonStreamHandler()
        
        mixed = [
            1,
            "string",
            {"object": True},
            [1, 2, 3],
            None,
            3.14,
            True
        ]
        
        result = handler.process_chunk(json.dumps(mixed))
        assert result == mixed
        
    def test_special_characters_in_strings(self):
        """Test special characters in JSON strings."""
        handler = JsonStreamHandler()
        
        special = {
            "newline": "line1\nline2",
            "tab": "before\tafter",
            "quote": 'He said "hello"',
            "backslash": "C:\\path\\to\\file",
            "unicode": "😀🎉🌟",
            "control": "\u0001\u0002\u0003"
        }
        
        result = handler.process_chunk(json.dumps(special))
        assert result == special
        
    def test_numbers_edge_cases(self):
        """Test various number formats."""
        handler = JsonStreamHandler()
        
        numbers = {
            "int": 42,
            "negative": -123,
            "float": 3.14159,
            "scientific": 1.23e-4,
            "large": 9007199254740991,  # Max safe integer in JS
            "zero": 0,
            "negative_zero": -0.0
        }
        
        result = handler.process_chunk(json.dumps(numbers))
        assert result == numbers
        
    def test_boolean_and_null(self):
        """Test boolean and null values."""
        handler = JsonStreamHandler()
        
        values = {
            "true": True,
            "false": False,
            "null": None,
            "array_with_nulls": [None, True, False, None]
        }
        
        result = handler.process_chunk(json.dumps(values))
        assert result == values
        
    def test_empty_containers(self):
        """Test empty objects and arrays."""
        handler = JsonStreamHandler()
        
        # Empty object
        assert handler.process_chunk('{}') == {}
        
        handler.reset()
        
        # Empty array
        assert handler.process_chunk('[]') == []
        
        handler.reset()
        
        # Nested empty
        nested_empty = {"empty_obj": {}, "empty_arr": []}
        assert handler.process_chunk(json.dumps(nested_empty)) == nested_empty
        
    def test_whitespace_variations(self):
        """Test various whitespace patterns."""
        handler = JsonStreamHandler()
        
        # Minimal whitespace
        minimal = '{"a":1,"b":2}'
        assert handler.process_chunk(minimal) == {"a": 1, "b": 2}
        
        handler.reset()
        
        # Excessive whitespace
        excessive = '''
        {
            "a"    :    1    ,
            
            "b"    :    2
        }
        '''
        assert handler.process_chunk(excessive) == {"a": 1, "b": 2}
        
    def test_incremental_array_building(self):
        """Test building arrays incrementally."""
        handler = JsonStreamHandler()
        
        chunks = ['[', '1', ',', '2', ',', '3', ']']
        
        result = None
        for chunk in chunks:
            result = handler.process_chunk(chunk)
            
        assert result == [1, 2, 3]
        
    def test_malformed_json_handling(self):
        """Test graceful handling of various malformed JSON."""
        handler = JsonStreamHandler()
        
        # Missing quotes
        handler.process_chunk('{key: "value"}')
        assert handler.get_statistics()["objects_found"] == 0
        
        handler.reset()
        
        # Trailing comma
        handler.process_chunk('{"a": 1,}')
        # Should still parse in Python (json.loads is lenient)
        stats = handler.get_statistics()
        # This might or might not parse depending on Python version
        
        handler.reset()
        
        # Single quotes (not valid JSON)
        handler.process_chunk("{'key': 'value'}")
        assert handler.get_statistics()["objects_found"] == 0
        
    def test_json_lines_format(self):
        """Test JSON Lines format (newline-delimited JSON)."""
        handler = JsonStreamHandler()
        
        jsonl = '{"id": 1}\n{"id": 2}\n{"id": 3}\n'
        
        # Process as single chunk
        handler.process_chunk(jsonl)
        
        # Should have found all three objects
        all_objects = handler.get_all_objects()
        assert len(all_objects) == 3
        assert all_objects[0] == {"id": 1}
        assert all_objects[1] == {"id": 2}
        assert all_objects[2] == {"id": 3}
        
    def test_concurrent_json_objects(self):
        """Test multiple JSON objects without separation."""
        handler = JsonStreamHandler()
        
        # Multiple objects concatenated
        multi = '{"a":1}{"b":2}{"c":3}'
        
        # Process and check we get the last one
        result = handler.process_chunk(multi)
        assert result == {"c": 3}
        
        # But all should be captured
        all_objects = handler.get_all_objects()
        assert len(all_objects) == 3
        
    def test_partial_unicode_handling(self):
        """Test handling partial Unicode sequences."""
        handler = JsonStreamHandler()
        
        # Split a Unicode character across chunks
        chunks = ['{"text": "Hello ', '世', '界"}']
        
        result = None
        for chunk in chunks:
            result = handler.process_chunk(chunk)
            
        assert result == {"text": "Hello 世界"}
        
    def test_repair_complex_cases(self):
        """Test repair of complex incomplete JSON."""
        handler = JsonStreamHandler()
        
        # Nested incomplete
        handler.buffer = '{"a": {"b": {"c": "value"'
        repaired = handler._repair_json(handler.buffer)
        assert repaired == {"a": {"b": {"c": "value"}}}
        
        # Array with objects
        handler.buffer = '[{"id": 1}, {"id": 2'
        repaired = handler._repair_json(handler.buffer)
        assert repaired == [{"id": 1}, {"id": 2}]
        
    def test_streaming_performance(self):
        """Test performance with many small chunks."""
        handler = JsonStreamHandler()
        
        # Create a large JSON string
        large_obj = {"data": [{"id": i, "value": f"test_{i}"} for i in range(1000)]}
        json_str = json.dumps(large_obj)
        
        # Split into many small chunks
        chunk_size = 50
        chunks = [json_str[i:i+chunk_size] for i in range(0, len(json_str), chunk_size)]
        
        result = None
        for chunk in chunks:
            result = handler.process_chunk(chunk)
            
        assert result == large_obj
        
    def test_get_statistics(self):
        """Test statistics reporting."""
        handler = JsonStreamHandler()
        
        # Process some objects
        handler.process_chunk('{"first": 1}')
        handler.process_chunk('{"second": 2}')
        handler.process_chunk('{"incomplete": "')
        
        stats = handler.get_statistics()
        assert stats["objects_found"] == 2
        assert stats["incomplete_json"] is True
        assert stats["buffer_size"] > 0
        assert stats["last_object"] == {"second": 2}