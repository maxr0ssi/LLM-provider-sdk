from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, List


@dataclass
class AgentMetrics:
    request_id: Optional[str]
    trace_id: Optional[str]
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    retries: int
    error_class: Optional[str]
    tools_used: List[str]


class MetricsSink(Protocol):
    async def record(self, metrics: AgentMetrics) -> None: ...
    async def flush(self) -> None: ...


