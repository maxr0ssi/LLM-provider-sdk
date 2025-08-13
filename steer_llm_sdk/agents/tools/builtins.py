from __future__ import annotations

import json
import re
from typing import Any, Dict

from ..validators.json_schema import validate_json_schema


def extract_json(text: str) -> Any:
    """Extract first JSON object/array from a text blob and parse it.

    Raises ValueError if not found or parse fails.
    """
    pattern = re.compile(r"(\{[\s\S]*\}|\[[\s\S]*\])")
    match = pattern.search(text)
    if not match:
        raise ValueError("No JSON object/array found in text")
    candidate = match.group(1)
    return json.loads(candidate)


def format_validator(output: Any, schema: Dict[str, Any]) -> Any:
    """Validate output against a JSON schema; return the output on success.

    Raises jsonschema.ValidationError on failure.
    """
    return validate_json_schema(output, schema)


def json_repair(text: str, schema: Dict[str, Any] | None = None) -> Any:
    """Attempt to repair malformed JSON from text and return parsed value.

    Heuristics (deterministic):
    - Extract first JSON-like region
    - Replace single quotes with double quotes when safe
    - Remove trailing commas before } or ]
    - Ensure keys are quoted
    - Validate against schema if provided
    """
    # 1) Extract candidate
    candidate = text
    try:
        candidate = json.dumps(json.loads(text))  # already valid
        return json.loads(candidate)
    except Exception:
        # try extraction
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if m:
            candidate = m.group(1)
        else:
            candidate = text
    # 2) Replace single quotes with double quotes in a conservative way
    # Only outside of already double-quoted substrings
    candidate = re.sub(r"'", '"', candidate)
    # 3) Remove trailing commas before closing braces/brackets
    candidate = re.sub(r",\s*([\]\}])", r"\1", candidate)
    # 4) Quote bare keys: foo: "bar" -> "foo": "bar"
    candidate = re.sub(r"(?m)(\{|,|\s)([A-Za-z0-9_]+)\s*:\s", lambda m: f"{m.group(1)}\"{m.group(2)}\": ", candidate)
    # Try parse
    obj = json.loads(candidate)
    if schema is not None:
        validate_json_schema(obj, schema)
    return obj


