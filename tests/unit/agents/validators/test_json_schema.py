"""
Unit tests for JSON schema validator.
"""

import json
import pytest
from jsonschema import ValidationError, SchemaError

from steer_llm_sdk.agents.validators.json_schema import (
    JsonSchemaValidator,
    validate_llm_json_output,
    attempt_json_repair,
    create_schema_from_example
)


class TestJsonSchemaValidator:
    """Test JsonSchemaValidator class."""
    
    def test_validate_valid_schema(self):
        """Test validating a well-formed schema."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }
        # Should not raise
        JsonSchemaValidator.validate_schema(schema)
    
    def test_validate_invalid_schema(self):
        """Test validating a malformed schema."""
        schema = {
            "type": "invalid-type",  # Invalid type
            "properties": "not-an-object"
        }
        with pytest.raises(SchemaError):
            JsonSchemaValidator.validate_schema(schema)
    
    def test_validate_data_valid(self):
        """Test validating data against schema - valid case."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        data = {"name": "Alice", "age": 30}
        
        result = JsonSchemaValidator.validate_data(data, schema)
        assert result == data  # Returns the same data if valid
    
    def test_validate_data_invalid(self):
        """Test validating data against schema - invalid case."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name", "age"]
        }
        data = {"name": "Alice"}  # Missing required 'age'
        
        with pytest.raises(ValidationError) as exc_info:
            JsonSchemaValidator.validate_data(data, schema)
        
        assert "root" in str(exc_info.value)
        assert "'age' is a required property" in str(exc_info.value)
    
    def test_validate_data_type_mismatch(self):
        """Test type mismatch validation."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"}
            }
        }
        data = {"count": "not-a-number"}
        
        with pytest.raises(ValidationError) as exc_info:
            JsonSchemaValidator.validate_data(data, schema)
        
        assert "count" in str(exc_info.value)
    
    def test_validate_json_string(self):
        """Test validating a JSON string."""
        schema = {
            "type": "array",
            "items": {"type": "number"}
        }
        json_string = "[1, 2, 3, 4]"
        
        result = JsonSchemaValidator.validate_json_string(json_string, schema)
        assert result == [1, 2, 3, 4]
    
    def test_validate_invalid_json_string(self):
        """Test validating malformed JSON string."""
        schema = {"type": "object"}
        json_string = "{invalid json"
        
        with pytest.raises(json.JSONDecodeError):
            JsonSchemaValidator.validate_json_string(json_string, schema)
    
    def test_get_schema_errors(self):
        """Test getting validation errors without raising."""
        schema = {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"}
            },
            "required": ["x", "y"]
        }
        data = {"x": "not-a-number"}  # Wrong type and missing y
        
        errors = JsonSchemaValidator.get_schema_errors(data, schema)
        assert len(errors) >= 2
        assert any("'y' is a required property" in e for e in errors)
        assert any("'not-a-number' is not of type 'number'" in e for e in errors)
    
    def test_extract_required_fields(self):
        """Test extracting required fields from schema."""
        schema = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "b": {"type": "string"},
                "c": {"type": "string"}
            },
            "required": ["a", "c"]
        }
        
        required = JsonSchemaValidator.extract_required_fields(schema)
        assert required == ["a", "c"]
    
    def test_extract_required_fields_non_object(self):
        """Test extracting required fields from non-object schema."""
        schema = {"type": "array"}
        required = JsonSchemaValidator.extract_required_fields(schema)
        assert required == []
    
    def test_is_valid(self):
        """Test is_valid helper method."""
        schema = {
            "type": "object",
            "properties": {
                "value": {"type": "boolean"}
            }
        }
        
        assert JsonSchemaValidator.is_valid({"value": True}, schema) is True
        assert JsonSchemaValidator.is_valid({"value": "not-bool"}, schema) is False
        
        # Test with actually invalid schema
        invalid_schema = {
            "type": "invalid-type",  # This will cause a schema error
            "properties": {}
        }
        assert JsonSchemaValidator.is_valid({"value": True}, invalid_schema) is False


class TestValidationHelpers:
    """Test validation helper functions."""
    
    def test_validate_llm_json_output_dict(self):
        """Test validating LLM output that's already a dict."""
        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string"}
            }
        }
        output = {"result": "success"}
        
        result = validate_llm_json_output(output, schema)
        assert result == output
    
    def test_validate_llm_json_output_string(self):
        """Test validating LLM output as JSON string."""
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "number"}
            }
        }
        output = '{"answer": 42}'
        
        result = validate_llm_json_output(output, schema)
        assert result == {"answer": 42}
    
    def test_validate_llm_json_output_with_repair(self):
        """Test validating with repair attempt."""
        schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string"}
            }
        }
        # Single quotes and trailing comma
        output = "{'key': 'value',}"
        
        result = validate_llm_json_output(output, schema, attempt_repair=True)
        assert result == {"key": "value"}
    
    def test_attempt_json_repair_quotes(self):
        """Test JSON repair for quote issues."""
        # Single quotes
        repaired = attempt_json_repair("{'key': 'value'}")
        assert '"key": "value"' in repaired
        
        # Unquoted keys
        repaired = attempt_json_repair("{key: 123}")
        assert '"key":' in repaired
    
    def test_attempt_json_repair_commas(self):
        """Test JSON repair for trailing commas."""
        # Trailing comma in object
        repaired = attempt_json_repair('{"a": 1, "b": 2,}')
        assert repaired == '{"a": 1, "b": 2}'
        
        # Trailing comma in array
        repaired = attempt_json_repair('[1, 2, 3,]')
        assert repaired == '[1, 2, 3]'
    
    def test_create_schema_from_example_simple(self):
        """Test creating schema from simple example."""
        example = {
            "name": "John",
            "age": 30,
            "active": True
        }
        
        schema = create_schema_from_example(example)
        assert schema["type"] == "object"
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["age"]["type"] == "integer"
        assert schema["properties"]["active"]["type"] == "boolean"
        assert set(schema["required"]) == {"name", "age", "active"}
    
    def test_create_schema_from_example_nested(self):
        """Test creating schema from nested example."""
        example = {
            "user": {
                "id": 123,
                "profile": {
                    "bio": "Hello"
                }
            },
            "tags": ["python", "ai"]
        }
        
        schema = create_schema_from_example(example)
        assert schema["properties"]["user"]["type"] == "object"
        assert schema["properties"]["user"]["properties"]["id"]["type"] == "integer"
        assert schema["properties"]["user"]["properties"]["profile"]["type"] == "object"
        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["tags"]["items"]["type"] == "string"
    
    def test_create_schema_from_example_array(self):
        """Test creating schema from array example."""
        example = [1, 2, 3]
        schema = create_schema_from_example(example)
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "integer"
    
    def test_create_schema_from_example_null(self):
        """Test creating schema with null values."""
        example = {"value": None}
        schema = create_schema_from_example(example)
        assert schema["properties"]["value"]["type"] == "null"