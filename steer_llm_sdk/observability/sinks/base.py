"""Base interface for metrics sinks."""

from typing import Protocol
from ..metrics import AgentMetrics


class MetricsSink(Protocol):
    """Protocol for metrics sink implementations."""
    
    async def record(self, metrics: AgentMetrics) -> None:
        """Record metrics data."""
        ...
    
    async def flush(self) -> None:
        """Flush any buffered metrics."""
        ...