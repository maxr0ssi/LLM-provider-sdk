from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, List


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


class MetricsSink(Protocol):
    async def record(self, metrics: AgentMetrics) -> None: ...
    async def flush(self) -> None: ...


