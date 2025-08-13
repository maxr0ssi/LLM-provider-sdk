from __future__ import annotations

import inspect
import typing as t


def schema_from_callable(func: t.Callable) -> dict:
    """Generate a minimal JSON schema for a Python callable’s keyword parameters.

    - Types: int, float, bool, str, list[T], dict map to JSON schema types.
    - Required: parameters without default values.
    - Best-effort; deterministic and conservative.
    """
    sig = inspect.signature(func)
    properties: dict[str, dict] = {}
    required: list[str] = []

    def map_type(ann: t.Any) -> dict:
        origin = t.get_origin(ann) or ann
        args = t.get_args(ann)
        if origin in (int,):
            return {"type": "integer"}
        if origin in (float,):
            return {"type": "number"}
        if origin in (bool,):
            return {"type": "boolean"}
        if origin in (str,):
            return {"type": "string"}
        if origin in (list, t.List):
            item_schema = {"type": "string"}
            if args:
                item_schema = map_type(args[0])
            return {"type": "array", "items": item_schema}
        if origin in (dict, t.Dict):
            return {"type": "object"}
        return {"type": "string"}

    for name, param in sig.parameters.items():
        if param.kind not in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            continue
        ann = param.annotation if param.annotation is not inspect._empty else str
        properties[name] = map_type(ann)
        if param.default is inspect._empty:
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


