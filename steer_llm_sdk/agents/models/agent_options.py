from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AgentOptions(BaseModel):
    streaming: bool = False
    deterministic: bool = False
    budget: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    trace_id: Optional[str] = None
    runtime: Optional[str] = None  # Agent runtime to use (e.g., 'openai_agents')


