from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RequestMetrics


@dataclass
class AgentMetrics:
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    model: str = ""
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    retries: int = 0
    error_class: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    agent_runtime: Optional[str] = None
    ttft_ms: Optional[int] = None
    tools_invoked: int = 0
    agent_loop_iters: int = 0

    @classmethod
    def from_request_metrics(cls, metrics: RequestMetrics) -> AgentMetrics:
        """Create AgentMetrics from RequestMetrics for compatibility."""
        return cls(
            request_id=metrics.request_id,
            model=metrics.model or "",
            latency_ms=int(metrics.duration_ms or 0),
            input_tokens=metrics.prompt_tokens,
            output_tokens=metrics.completion_tokens,
            cached_tokens=metrics.cached_tokens,
            retries=0,
            error_class=None,
            tools_used=[]
        )


