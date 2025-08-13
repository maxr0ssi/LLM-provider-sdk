from __future__ import annotations

from typing import Any, Dict
from jsonschema import Draft202012Validator, ValidationError


def validate_json_schema(data: Any, schema: Dict[str, Any]) -> Any:
    """Validate `data` against a JSON schema, raising ValidationError on failure."""
    validator = Draft202012Validator(schema)
    validator.validate(data)
    return data

"""
JSON schema validation utilities for agent outputs.

Provides strict validation of LLM outputs against JSON schemas
with detailed error messages for debugging.
"""

import json
from typing import Any, Dict, List, Optional, Union
from jsonschema import validate, ValidationError, Draft7Validator
from jsonschema.exceptions import SchemaError


class JsonSchemaValidator:
    """Validates data against JSON schemas with helpful error messages."""
    
    @staticmethod
    def validate_schema(schema: Dict[str, Any]) -> None:
        """
        Validate that a schema is well-formed.
        
        Args:
            schema: JSON schema to validate
            
        Raises:
            SchemaError: If the schema itself is invalid
        """
        try:
            Draft7Validator.check_schema(schema)
        except SchemaError as e:
            raise SchemaError(f"Invalid JSON schema: {str(e)}")
    
    @staticmethod
    def validate_data(data: Any, schema: Dict[str, Any]) -> Any:
        """
        Validate data against a JSON schema.
        
        Args:
            data: Data to validate
            schema: JSON schema to validate against
            
        Returns:
            The validated data (unchanged if valid)
            
        Raises:
            ValidationError: If data doesn't match schema
            SchemaError: If the schema itself is invalid
        """
        # First validate the schema
        JsonSchemaValidator.validate_schema(schema)
        
        # Then validate the data
        try:
            validate(instance=data, schema=schema)
            return data
        except ValidationError as e:
            # Build a helpful error message
            error_path = " -> ".join(str(p) for p in e.path) if e.path else "root"
            raise ValidationError(
                f"Validation error at {error_path}: {e.message}\n"
                f"Failed validating {e.validator!r} in schema"
            )
    
    @staticmethod
    def validate_json_string(json_string: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and validate a JSON string against a schema.
        
        Args:
            json_string: JSON string to parse and validate
            schema: JSON schema to validate against
            
        Returns:
            The parsed and validated data
            
        Raises:
            json.JSONDecodeError: If the string is not valid JSON
            ValidationError: If parsed data doesn't match schema
            SchemaError: If the schema itself is invalid
        """
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON at position {e.pos}: {e.msg}",
                e.doc, e.pos
            )
        
        return JsonSchemaValidator.validate_data(data, schema)
    
    @staticmethod
    def get_schema_errors(data: Any, schema: Dict[str, Any]) -> List[str]:
        """
        Get all validation errors without raising an exception.
        
        Args:
            data: Data to validate
            schema: JSON schema to validate against
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Check schema validity
        try:
            JsonSchemaValidator.validate_schema(schema)
        except SchemaError as e:
            return [f"Schema error: {str(e)}"]
        
        # Collect all validation errors
        validator = Draft7Validator(schema)
        for error in validator.iter_errors(data):
            error_path = " -> ".join(str(p) for p in error.path) if error.path else "root"
            errors.append(f"{error_path}: {error.message}")
        
        return errors
    
    @staticmethod
    def extract_required_fields(schema: Dict[str, Any]) -> List[str]:
        """
        Extract required fields from a JSON schema.
        
        Args:
            schema: JSON schema
            
        Returns:
            List of required field names at the root level
        """
        if schema.get("type") != "object":
            return []
        
        return schema.get("required", [])
    
    @staticmethod
    def is_valid(data: Any, schema: Dict[str, Any]) -> bool:
        """
        Check if data is valid against a schema without raising exceptions.
        
        Args:
            data: Data to validate
            schema: JSON schema to validate against
            
        Returns:
            True if valid, False otherwise
        """
        try:
            JsonSchemaValidator.validate_data(data, schema)
            return True
        except (ValidationError, SchemaError, Exception):
            return False


# Helper functions for common validation patterns

def validate_llm_json_output(
    output: Union[str, Dict[str, Any]], 
    expected_schema: Dict[str, Any],
    attempt_repair: bool = False
) -> Dict[str, Any]:
    """
    Validate LLM output against a JSON schema with optional repair attempts.
    
    Args:
        output: LLM output (string or already parsed dict)
        expected_schema: JSON schema to validate against
        attempt_repair: Whether to attempt basic JSON repair
        
    Returns:
        Validated data as a dictionary
        
    Raises:
        ValidationError: If validation fails
        json.JSONDecodeError: If JSON parsing fails
    """
    # If output is a string, try to parse it
    if isinstance(output, str):
        if attempt_repair:
            output = attempt_json_repair(output)
        data = json.loads(output)
    else:
        data = output
    
    # Validate against schema
    return JsonSchemaValidator.validate_data(data, expected_schema)


def attempt_json_repair(json_string: str) -> str:
    """
    Attempt basic repairs on malformed JSON.
    
    Common LLM errors:
    - Missing quotes around keys
    - Trailing commas
    - Single quotes instead of double quotes
    - Unescaped newlines in strings
    
    Args:
        json_string: Potentially malformed JSON string
        
    Returns:
        Repaired JSON string (best effort)
    """
    # This is a simple implementation - can be enhanced with more sophisticated repair
    repaired = json_string
    
    # Replace single quotes with double quotes (naive approach)
    # In production, use a proper parser to avoid replacing quotes in values
    repaired = repaired.replace("'", '"')
    
    # Remove trailing commas before } or ]
    import re
    repaired = re.sub(r',\s*}', '}', repaired)
    repaired = re.sub(r',\s*]', ']', repaired)
    
    # Try to fix unquoted keys (very basic)
    # This is a simplified approach - in production use a proper JSON repair library
    repaired = re.sub(r'(\w+):', r'"\1":', repaired)
    
    return repaired


def create_schema_from_example(example: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a basic JSON schema from an example object.
    
    This is useful for quick prototyping when you have an example
    of the expected output but not a formal schema.
    
    Args:
        example: Example data to create schema from
        
    Returns:
        JSON schema that would validate the example
    """
    def infer_type(value: Any) -> Dict[str, Any]:
        if value is None:
            return {"type": "null"}
        elif isinstance(value, bool):
            return {"type": "boolean"}
        elif isinstance(value, int):
            return {"type": "integer"}
        elif isinstance(value, float):
            return {"type": "number"}
        elif isinstance(value, str):
            return {"type": "string"}
        elif isinstance(value, list):
            if value:
                # Infer from first item
                return {
                    "type": "array",
                    "items": infer_type(value[0])
                }
            else:
                return {"type": "array"}
        elif isinstance(value, dict):
            properties = {}
            required = []
            for k, v in value.items():
                properties[k] = infer_type(v)
                required.append(k)
            return {
                "type": "object",
                "properties": properties,
                "required": required
            }
        else:
            return {}
    
    schema = infer_type(example)
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    return schema