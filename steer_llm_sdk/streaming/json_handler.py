"""
JSON stream handler for processing streaming JSON responses.

This module provides robust JSON parsing for streaming responses,
handling partial chunks, nested objects, and arrays.
"""

from typing import List, Dict, Any, Optional, Union
import json
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class JsonTokenType(Enum):
    """Types of JSON tokens."""
    OBJECT_START = "{"
    OBJECT_END = "}"
    ARRAY_START = "["
    ARRAY_END = "]"
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"


class JsonStreamHandler:
    """
    Handles JSON streaming with proper parsing and deduplication.
    
    This handler can process streaming JSON chunks and extract complete
    objects or arrays, handling nested structures and partial data.
    """
    
    def __init__(self):
        """Initialize the JSON stream handler."""
        self.buffer = ""
        self.objects: List[Union[Dict[str, Any], List[Any]]] = []
        self.depth = 0
        self.in_string = False
        self.escape_next = False
        self.start_chars = {'{', '['}
        self.end_chars = {'}', ']'}
        self.matching_pairs = {'{': '}', '[': ']'}
        self.stack: List[str] = []
        
    def process_chunk(self, chunk: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """
        Process a streaming chunk and return complete JSON if found.
        
        Args:
            chunk: A chunk of text that may contain partial or complete JSON
            
        Returns:
            The most recent complete JSON object/array if found, None otherwise
        """
        if not chunk:
            return None
            
        self.buffer += chunk
        
        # Try to extract complete JSON objects
        extracted = self._extract_json_objects()
        if extracted:
            # Return the most recent complete object
            return extracted[-1]
        return None
    
    def get_all_objects(self) -> List[Union[Dict[str, Any], List[Any]]]:
        """
        Get all objects found so far.
        
        Returns:
            List of all complete JSON objects/arrays found
        """
        return self.objects.copy()
    
    def _extract_json_objects(self) -> List[Union[Dict[str, Any], List[Any]]]:
        """
        Extract all complete JSON objects or arrays from buffer.
        
        Returns:
            List of complete JSON objects/arrays found
        """
        objects = []
        i = 0
        
        while i < len(self.buffer):
            # Skip whitespace
            while i < len(self.buffer) and self.buffer[i].isspace():
                i += 1
            
            if i >= len(self.buffer):
                break
                
            # Look for start of JSON object or array
            if self.buffer[i] in self.start_chars:
                start_idx = i
                end_idx = self._find_json_end(i)
                
                if end_idx is not None:
                    # Found complete JSON
                    json_str = self.buffer[start_idx:end_idx + 1]
                    try:
                        obj = json.loads(json_str)
                        objects.append(obj)
                        self.objects.append(obj)
                        # Move past this JSON
                        i = end_idx + 1
                    except json.JSONDecodeError as e:
                        logger.debug(f"Failed to parse JSON: {e}")
                        # Skip this character and continue
                        i += 1
                else:
                    # Incomplete JSON, keep in buffer
                    self.buffer = self.buffer[start_idx:]
                    break
            else:
                # Not JSON, skip character
                i += 1
        
        # Update buffer to remove processed content
        if i < len(self.buffer):
            if i > 0:
                self.buffer = self.buffer[i:]
        else:
            self.buffer = ""
            
        return objects
    
    def _find_json_end(self, start_idx: int) -> Optional[int]:
        """
        Find the end of a JSON object/array starting at start_idx.
        
        Args:
            start_idx: Starting position in buffer
            
        Returns:
            End index if complete JSON found, None otherwise
        """
        if start_idx >= len(self.buffer):
            return None
            
        stack = []
        in_string = False
        escape_next = False
        
        start_char = self.buffer[start_idx]
        if start_char not in self.start_chars:
            return None
            
        stack.append(start_char)
        i = start_idx + 1
        
        while i < len(self.buffer) and stack:
            char = self.buffer[i]
            
            if escape_next:
                escape_next = False
                i += 1
                continue
                
            if char == '\\' and in_string:
                escape_next = True
                i += 1
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                i += 1
                continue
                
            if in_string:
                i += 1
                continue
                
            if char in self.start_chars:
                stack.append(char)
            elif char in self.end_chars:
                if not stack:
                    return None
                    
                expected_end = self.matching_pairs.get(stack[-1])
                if char == expected_end:
                    stack.pop()
                    if not stack:
                        return i
                else:
                    # Mismatched brackets
                    return None
                    
            i += 1
            
        return None
    
    def get_final_object(self) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """
        Get the final complete object or attempt to parse remaining buffer.
        
        Returns:
            The last complete JSON object/array, or None if none found
        """
        # First check if we have any complete objects
        if self.objects:
            return self.objects[-1]
            
        # Try to parse remaining buffer
        if self.buffer.strip():
            # Try to extract any remaining complete JSON
            extracted = self._extract_json_objects()
            if extracted:
                return extracted[-1]
                
            # Last resort: try to repair and parse
            repaired = self._repair_json(self.buffer)
            if repaired:
                return repaired
                
        return None
    
    def _repair_json(self, json_str: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """
        Attempt to repair incomplete JSON.
        
        Args:
            json_str: Potentially incomplete JSON string
            
        Returns:
            Parsed JSON if repair successful, None otherwise
        """
        json_str = json_str.strip()
        if not json_str:
            return None
            
        # Count brackets
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        
        # Add missing closing brackets/braces
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
        if open_brackets > close_brackets:
            json_str += ']' * (open_brackets - close_brackets)
            
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try adding quotes to unquoted strings
            # This is a very basic repair attempt
            try:
                # Replace common patterns
                import re
                # Add quotes around unquoted keys
                json_str = re.sub(r'(\w+):', r'"\1":', json_str)
                return json.loads(json_str)
            except:
                return None
    
    def reset(self):
        """Reset the handler state."""
        self.buffer = ""
        self.objects = []
        self.depth = 0
        self.in_string = False
        self.escape_next = False
        self.stack = []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about processing.
        
        Returns:
            Dictionary with processing statistics
        """
        return {
            "buffer_size": len(self.buffer),
            "objects_found": len(self.objects),
            "incomplete_json": bool(self.buffer.strip()),
            "last_object": self.objects[-1] if self.objects else None
        }