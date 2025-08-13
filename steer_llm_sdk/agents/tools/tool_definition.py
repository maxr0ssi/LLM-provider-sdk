from __future__ import annotations

from typing import Any, Dict, Callable
from pydantic import BaseModel, Field


class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    handler: Callable
    deterministic: bool = True


