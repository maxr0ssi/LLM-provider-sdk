"""
Metrics collector for gathering and dispatching metrics to sinks.

This module provides the core metrics collection infrastructure that integrates
with the router, client, and streaming components to gather comprehensive metrics.
"""

from __future__ import annotations

import asyncio
import time
import logging
from typing import Optional, List, Dict, Any, Protocol, Set
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import uuid

from .models import (
    BaseMetrics, RequestMetrics, StreamingMetrics, 
    ReliabilityMetrics, UsageMetrics, ErrorMetrics,
    MetricsBatch, AgentMetrics
)
from .sinks.base import MetricsSink


logger = logging.getLogger(__name__)


class MetricsFilter(Protocol):
    """Protocol for filtering metrics before they're sent to sinks."""
    
    def should_collect(self, metric: BaseMetrics) -> bool:
        """Return True if this metric should be collected."""
        ...


@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""
    enabled: bool = True
    batch_size: int = 100
    batch_timeout_seconds: float = 1.0
    enable_streaming_metrics: bool = True
    enable_reliability_metrics: bool = True
    enable_cost_tracking: bool = False
    filters: List[MetricsFilter] = field(default_factory=list)
    
    # Sampling rates (0.0 to 1.0)
    request_sampling_rate: float = 1.0
    streaming_sampling_rate: float = 1.0
    error_sampling_rate: float = 1.0


class MetricsCollector:
    """
    Central metrics collector that gathers metrics from across the SDK.
    
    Features:
    - Async batch collection for performance
    - Multiple sink support
    - Filtering and sampling
    - Request context tracking
    """
    
    def __init__(self, config: Optional[MetricsConfig] = None):
        """
        Initialize the metrics collector.
        
        Args:
            config: Configuration for metrics collection
        """
        self.config = config or MetricsConfig()
        self.sinks: List[MetricsSink] = []
        self._batch = MetricsBatch()
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
        self._active_requests: Dict[str, RequestMetrics] = {}
        self._shutdown = False
        
        # Start batch processor if enabled
        if self.config.enabled and self.config.batch_size > 1:
            self._start_batch_processor()
    
    def add_sink(self, sink: MetricsSink) -> None:
        """Add a metrics sink."""
        self.sinks.append(sink)
        logger.debug(f"Added metrics sink: {type(sink).__name__}")
    
    def remove_sink(self, sink: MetricsSink) -> None:
        """Remove a metrics sink."""
        if sink in self.sinks:
            self.sinks.remove(sink)
            logger.debug(f"Removed metrics sink: {type(sink).__name__}")
    
    async def record(self, metric: BaseMetrics) -> None:
        """
        Record a metric.
        
        Args:
            metric: The metric to record
        """
        if not self.config.enabled:
            return
        
        # Apply filters
        for filter in self.config.filters:
            if not filter.should_collect(metric):
                return
        
        # Apply sampling
        if not self._should_sample(metric):
            return
        
        # Add to batch or send directly
        if self.config.batch_size > 1:
            await self._add_to_batch(metric)
        else:
            await self._send_to_sinks(metric)
    
    @asynccontextmanager
    async def track_request(
        self,
        provider: str,
        model: str,
        method: str = "generate",
        request_id: Optional[str] = None
    ):
        """
        Context manager for tracking request metrics.
        
        Args:
            provider: Provider name
            model: Model name
            method: Method being called (generate, stream, etc.)
            request_id: Optional request ID
            
        Yields:
            RequestMetrics object that can be updated
        """
        if not self.config.enabled:
            yield RequestMetrics()
            return
        
        request_id = request_id or str(uuid.uuid4())[:8]
        start_time = time.time()
        
        metrics = RequestMetrics(
            provider=provider,
            model=model,
            method=method,
            request_id=request_id,
            timestamp=start_time
        )
        
        self._active_requests[request_id] = metrics
        
        try:
            yield metrics
            
            # Calculate duration
            metrics.duration_ms = (time.time() - start_time) * 1000
            
            # Record the completed request
            await self.record(metrics)
            
        except Exception as e:
            # Record error metrics
            error_metrics = ErrorMetrics(
                provider=provider,
                model=model,
                request_id=request_id,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            await self.record(error_metrics)
            raise
        finally:
            # Clean up
            self._active_requests.pop(request_id, None)
    
    async def record_streaming_metrics(
        self,
        request_id: str,
        streaming_metrics: Dict[str, Any]
    ) -> None:
        """
        Record streaming metrics for a request.
        
        Args:
            request_id: Request ID
            streaming_metrics: Raw streaming metrics from StreamAdapter
        """
        if not self.config.enabled or not self.config.enable_streaming_metrics:
            return
        
        # Get associated request metrics if available
        request_metrics = self._active_requests.get(request_id)
        
        metrics = StreamingMetrics(
            request_id=request_id,
            provider=request_metrics.provider if request_metrics else None,
            model=request_metrics.model if request_metrics else None,
            total_chunks=streaming_metrics.get("chunks", 0),
            total_chars=streaming_metrics.get("total_chars", 0),
            chunks_per_second=streaming_metrics.get("chunks_per_second", 0),
            chars_per_second=streaming_metrics.get("chars_per_second", 0),
            streaming_duration_ms=streaming_metrics.get("duration_seconds", 0) * 1000,
            json_objects_found=streaming_metrics.get("json_objects_found", 0),
            aggregation_method=streaming_metrics.get("aggregation_method"),
            aggregation_confidence=streaming_metrics.get("aggregation_confidence")
        )
        
        await self.record(metrics)
    
    async def record_reliability_metrics(
        self,
        request_id: str,
        retry_attempts: int = 0,
        retry_succeeded: bool = False,
        total_retry_delay_ms: float = 0,
        circuit_breaker_state: Optional[str] = None,
        error_type: Optional[str] = None,
        error_category: Optional[str] = None,
        is_retryable: bool = False
    ) -> None:
        """Record reliability-related metrics."""
        if not self.config.enabled or not self.config.enable_reliability_metrics:
            return
        
        # Get associated request metrics if available
        request_metrics = self._active_requests.get(request_id)
        
        metrics = ReliabilityMetrics(
            request_id=request_id,
            provider=request_metrics.provider if request_metrics else None,
            model=request_metrics.model if request_metrics else None,
            retry_attempts=retry_attempts,
            retry_succeeded=retry_succeeded,
            total_retry_delay_ms=total_retry_delay_ms,
            circuit_breaker_state=circuit_breaker_state,
            error_type=error_type,
            error_category=error_category,
            is_retryable=is_retryable
        )
        
        await self.record(metrics)
    
    async def get_usage_summary(
        self,
        window_seconds: float = 60.0,
        provider: Optional[str] = None
    ) -> UsageMetrics:
        """
        Get usage summary for a time window.
        
        Args:
            window_seconds: Time window in seconds
            provider: Optional provider filter
            
        Returns:
            UsageMetrics summary
        """
        # This would typically query from sinks that support aggregation
        # For now, return empty metrics
        return UsageMetrics(
            window_duration_seconds=window_seconds,
            provider=provider
        )
    
    async def flush(self) -> None:
        """Flush all pending metrics to sinks."""
        if self._batch.size() > 0:
            await self._flush_batch()
        
        # Flush all sinks
        for sink in self.sinks:
            try:
                await sink.flush()
            except Exception as e:
                logger.error(f"Error flushing sink {type(sink).__name__}: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the metrics collector."""
        self._shutdown = True
        
        # Stop batch processor
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
        
        # Final flush
        await self.flush()
    
    # Private methods
    
    def _should_sample(self, metric: BaseMetrics) -> bool:
        """Check if a metric should be sampled."""
        import random
        
        if isinstance(metric, RequestMetrics):
            return random.random() < self.config.request_sampling_rate
        elif isinstance(metric, StreamingMetrics):
            return random.random() < self.config.streaming_sampling_rate
        elif isinstance(metric, ErrorMetrics):
            return random.random() < self.config.error_sampling_rate
        
        return True
    
    async def _add_to_batch(self, metric: BaseMetrics) -> None:
        """Add a metric to the batch."""
        async with self._batch_lock:
            self._batch.add(metric)
            
            if self._batch.size() >= self.config.batch_size:
                await self._flush_batch()
    
    async def _flush_batch(self) -> None:
        """Flush the current batch to sinks."""
        if self._batch.size() == 0:
            return
        
        # Create new batch and swap
        async with self._batch_lock:
            current_batch = self._batch
            self._batch = MetricsBatch()
        
        # Send to all sinks
        for metric in current_batch.metrics:
            await self._send_to_sinks(metric)
    
    async def _send_to_sinks(self, metric: BaseMetrics) -> None:
        """Send a metric to all sinks."""
        # Convert to AgentMetrics for backward compatibility if needed
        if isinstance(metric, RequestMetrics):
            agent_metrics = AgentMetrics.from_request_metrics(metric)
            
            for sink in self.sinks:
                try:
                    await sink.record(agent_metrics)
                except Exception as e:
                    logger.error(f"Error sending metric to {type(sink).__name__}: {e}")
    
    def _start_batch_processor(self) -> None:
        """Start the background batch processor."""
        async def batch_processor():
            while not self._shutdown:
                try:
                    await asyncio.sleep(self.config.batch_timeout_seconds)
                    await self._flush_batch()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in batch processor: {e}")
        
        self._batch_task = asyncio.create_task(batch_processor())


# Global collector instance
_global_collector: Optional[MetricsCollector] = None


def get_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def set_collector(collector: MetricsCollector) -> None:
    """Set the global metrics collector instance."""
    global _global_collector
    _global_collector = collector