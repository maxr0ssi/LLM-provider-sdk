from __future__ import annotations

from typing import Any, Dict
from jsonschema import Draft202012Validator
from .tool_definition import Tool


class ToolExecutor:
    def __init__(self) -> None:
        pass

    def execute(self, tool: Tool, args: Dict[str, Any]) -> Any:
        if tool.parameters:
            Draft202012Validator(tool.parameters).validate(args)
        return tool.handler(**args)


