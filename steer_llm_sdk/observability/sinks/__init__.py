"""Metrics sinks for exporting observability data.

Available sinks:
- OTLP (OpenTelemetry Protocol)
- Custom implementations via MetricsSink protocol
"""

from .base import MetricsSink
from .otlp import OTLPSink

__all__ = ["MetricsSink", "OTLPSink"]