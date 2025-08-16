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
    agent_runtime: Optional[str] = None  # Runtime used (e.g., 'openai_agents')
    ttft_ms: Optional[int] = None  # Time to first token (streaming)
    tools_invoked: int = 0  # Number of tool invocations
    agent_loop_iters: int = 0  # Number of agent loop iterations


class MetricsSink(Protocol):
    async def record(self, metrics: AgentMetrics) -> None: ...
    async def flush(self) -> None: ...


