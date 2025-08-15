"""Metrics sinks for exporting observability data.

Available sinks:
- InMemory (for testing and debugging)
- OTLP (OpenTelemetry Protocol)
- Custom implementations via MetricsSink protocol
"""

from .base import MetricsSink
from .otlp import OTelMetricsSink
from .in_memory import InMemoryMetricsSink

__all__ = ["MetricsSink", "OTelMetricsSink", "InMemoryMetricsSink"]