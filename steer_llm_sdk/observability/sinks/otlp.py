from __future__ import annotations

from typing import Optional
from .metrics import AgentMetrics, MetricsSink


class OTelMetricsSink(MetricsSink):
    """Optional OpenTelemetry metrics sink (best-effort, no hard dep).

    If opentelemetry-api is unavailable, calls are no-ops.
    """

    def __init__(self) -> None:
        try:
            from opentelemetry import metrics  # type: ignore
        except Exception:
            self.enabled = False
            self._meter = None
            self._hist_latency = None
            self._counter_requests = None
            return

        self.enabled = True
        self._meter = metrics.get_meter("steer_llm_sdk")
        # Define instruments (names kept stable)
        self._hist_latency = self._meter.create_histogram("sdk_request_latency_ms")
        self._counter_requests = self._meter.create_counter("sdk_requests_total")

    async def record(self, metrics: AgentMetrics) -> None:  # type: ignore[override]
        if not self.enabled:
            return
        attrs = {
            "model": metrics.model,
            "error_class": metrics.error_class or "none",
        }
        try:
            self._hist_latency.record(metrics.latency_ms, attrs)
            self._counter_requests.add(1, attrs)
        except Exception:
            # best-effort; do not raise
            return

    async def flush(self) -> None:  # type: ignore[override]
        # No-op; rely on OTel exporters
        return


