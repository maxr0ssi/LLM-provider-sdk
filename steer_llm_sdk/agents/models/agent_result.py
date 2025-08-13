from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    content: Any
    usage: Dict[str, Any] = Field(default_factory=dict)
    model: str
    elapsed_ms: int
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    confidence: Optional[float] = None


