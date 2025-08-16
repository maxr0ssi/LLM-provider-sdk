from __future__ import annotations

from typing import Optional, Dict, Any
import logging
from ..metrics import AgentMetrics
from .base import MetricsSink

logger = logging.getLogger(__name__)


class OTelMetricsSink(MetricsSink):
    """Optional OpenTelemetry metrics sink (best-effort, no hard dep).

    If opentelemetry-api is unavailable, calls are no-ops.
    """

    def __init__(self, service_name: str = "steer_llm_sdk", namespace: str = "llm") -> None:
        """
        Initialize OTLP metrics sink.
        
        Args:
            service_name: Service name for metrics
            namespace: Metric namespace prefix
        """
        self.service_name = service_name
        self.namespace = namespace
        
        try:
            from opentelemetry import metrics  # type: ignore
        except Exception:
            logger.warning("OpenTelemetry not available, metrics will be disabled")
            self.enabled = False
            self._meter = None
            self._instruments = {}
            return

        self.enabled = True
        self._meter = metrics.get_meter(
            name=service_name,
            version="1.0.0"
        )
        
        # Create instruments
        self._instruments = {
            # Histograms
            "request_duration": self._meter.create_histogram(
                name=f"{namespace}.request.duration",
                unit="ms",
                description="Request duration in milliseconds"
            ),
            "ttft": self._meter.create_histogram(
                name=f"{namespace}.streaming.ttft",
                unit="ms", 
                description="Time to first token"
            ),
            
            # Counters
            "requests_total": self._meter.create_counter(
                name=f"{namespace}.requests.total",
                unit="1",
                description="Total number of requests"
            ),
            "tokens_total": self._meter.create_counter(
                name=f"{namespace}.tokens.total",
                unit="1",
                description="Total tokens processed"
            ),
            "errors_total": self._meter.create_counter(
                name=f"{namespace}.errors.total",
                unit="1",
                description="Total number of errors"
            ),
            "retries_total": self._meter.create_counter(
                name=f"{namespace}.retries.total",
                unit="1",
                description="Total retry attempts"
            ),
            
            # Gauges (using UpDownCounter for simplicity)
            "active_requests": self._meter.create_up_down_counter(
                name=f"{namespace}.requests.active",
                unit="1",
                description="Number of active requests"
            ),
            "circuit_breaker_open": self._meter.create_up_down_counter(
                name=f"{namespace}.circuit_breaker.open",
                unit="1",
                description="Number of open circuit breakers"
            ),
        }
        
        logger.info(f"Initialized OTLP metrics sink for {service_name}")

    async def record(self, metrics: AgentMetrics) -> None:  # type: ignore[override]
        if not self.enabled:
            return
            
        # Extract provider from model name
        provider = self._extract_provider(metrics.model)
        
        # Common attributes
        attrs = {
            "provider": provider,
            "model": metrics.model,
            "error_class": metrics.error_class or "none",
            "has_error": "true" if metrics.error_class else "false",
        }
        
        try:
            # Request metrics
            self._instruments["request_duration"].record(metrics.latency_ms, attrs)
            self._instruments["requests_total"].add(1, attrs)
            
            # Token metrics
            token_attrs = {**attrs, "token_type": "input"}
            self._instruments["tokens_total"].add(metrics.input_tokens, token_attrs)
            
            token_attrs["token_type"] = "output"
            self._instruments["tokens_total"].add(metrics.output_tokens, token_attrs)
            
            if metrics.cached_tokens > 0:
                token_attrs["token_type"] = "cached"
                self._instruments["tokens_total"].add(metrics.cached_tokens, token_attrs)
            
            # Error metrics
            if metrics.error_class:
                self._instruments["errors_total"].add(1, attrs)
            
            # Retry metrics
            if metrics.retries > 0:
                retry_attrs = {**attrs, "retry_count": str(metrics.retries)}
                self._instruments["retries_total"].add(metrics.retries, retry_attrs)
                
        except Exception as e:
            # Best-effort; log but don't raise
            logger.debug(f"Failed to record OTLP metrics: {e}")
            return
    
    def record_streaming_metrics(self, metrics: Dict[str, Any]) -> None:
        """Record streaming-specific metrics."""
        if not self.enabled:
            return
            
        try:
            attrs = {
                "provider": metrics.get("provider", "unknown"),
                "model": metrics.get("model", "unknown"),
            }
            
            # Time to first token
            if "first_chunk_latency_ms" in metrics:
                self._instruments["ttft"].record(
                    metrics["first_chunk_latency_ms"], 
                    attrs
                )
                
        except Exception as e:
            logger.debug(f"Failed to record streaming metrics: {e}")
    
    def record_circuit_breaker_state(self, provider: str, is_open: bool) -> None:
        """Record circuit breaker state change."""
        if not self.enabled:
            return
            
        try:
            attrs = {"provider": provider}
            # +1 for open, -1 for close
            self._instruments["circuit_breaker_open"].add(
                1 if is_open else -1,
                attrs
            )
        except Exception as e:
            logger.debug(f"Failed to record circuit breaker state: {e}")
    
    def _extract_provider(self, model: str) -> str:
        """Extract provider from model name."""
        if model.startswith("gpt"):
            return "openai"
        elif model.startswith("claude"):
            return "anthropic"
        elif model.startswith("grok"):
            return "xai"
        else:
            return "unknown"

    async def flush(self) -> None:  # type: ignore[override]
        # No-op; rely on OTel exporters
        return


