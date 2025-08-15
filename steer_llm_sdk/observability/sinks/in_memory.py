"""
In-memory metrics sink for testing and debugging.

This sink stores metrics in memory and provides query capabilities,
useful for testing, debugging, and local development.
"""

from __future__ import annotations

import time
import asyncio
from typing import List, Dict, Any, Optional, Callable
from collections import defaultdict, deque
from dataclasses import dataclass, field
import statistics

from ..metrics import AgentMetrics
from .base import MetricsSink


@dataclass
class MetricsSummary:
    """Summary statistics for a set of metrics."""
    count: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    error_rate: float = 0.0
    providers: Dict[str, int] = field(default_factory=dict)
    models: Dict[str, int] = field(default_factory=dict)
    errors: Dict[str, int] = field(default_factory=dict)


class InMemoryMetricsSink(MetricsSink):
    """
    In-memory metrics storage with query capabilities.
    
    Features:
    - Fixed-size circular buffer for memory efficiency
    - Time-based windowing
    - Aggregation and summary statistics
    - Query filtering
    """
    
    def __init__(self, max_size: int = 10000, ttl_seconds: float = 3600):
        """
        Initialize the in-memory sink.
        
        Args:
            max_size: Maximum number of metrics to store
            ttl_seconds: Time-to-live for metrics in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._metrics: deque[Tuple[float, AgentMetrics]] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
        
        # Indexes for fast lookup
        self._by_provider: Dict[str, List[AgentMetrics]] = defaultdict(list)
        self._by_model: Dict[str, List[AgentMetrics]] = defaultdict(list)
        self._by_request: Dict[str, AgentMetrics] = {}
        
        # Real-time aggregates
        self._total_requests = 0
        self._total_errors = 0
        self._total_tokens = 0
        self._total_latency_ms = 0
    
    async def record(self, metrics: AgentMetrics) -> None:
        """Record a metric."""
        async with self._lock:
            current_time = time.time()
            
            # Add to main storage
            self._metrics.append((current_time, metrics))
            
            # Update indexes
            provider = self._extract_provider(metrics.model)
            self._by_provider[provider].append(metrics)
            self._by_model[metrics.model].append(metrics)
            if metrics.request_id:
                self._by_request[metrics.request_id] = metrics
            
            # Update aggregates
            self._total_requests += 1
            if metrics.error_class:
                self._total_errors += 1
            self._total_tokens += (metrics.input_tokens + metrics.output_tokens)
            self._total_latency_ms += metrics.latency_ms
            
            # Clean up old entries
            await self._cleanup_old_metrics(current_time)
    
    async def flush(self) -> None:
        """No-op for in-memory sink."""
        pass
    
    async def get_metrics(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        request_id: Optional[str] = None,
        limit: int = 1000
    ) -> List[AgentMetrics]:
        """
        Query metrics with filters.
        
        Args:
            start_time: Start timestamp (Unix time)
            end_time: End timestamp (Unix time)
            provider: Filter by provider
            model: Filter by model
            request_id: Filter by request ID
            limit: Maximum number of results
            
        Returns:
            List of matching metrics
        """
        async with self._lock:
            results = []
            
            # Quick lookup by request ID
            if request_id and request_id in self._by_request:
                return [self._by_request[request_id]]
            
            # Filter metrics
            current_time = time.time()
            for timestamp, metric in self._metrics:
                # Time filter
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue
                
                # TTL check
                if current_time - timestamp > self.ttl_seconds:
                    continue
                
                # Provider filter
                if provider and self._extract_provider(metric.model) != provider:
                    continue
                
                # Model filter
                if model and metric.model != model:
                    continue
                
                results.append(metric)
                
                if len(results) >= limit:
                    break
            
            return results
    
    async def get_summary(
        self,
        window_seconds: float = 300,
        provider: Optional[str] = None
    ) -> MetricsSummary:
        """
        Get summary statistics for a time window.
        
        Args:
            window_seconds: Time window in seconds (default 5 minutes)
            provider: Optional provider filter
            
        Returns:
            Summary statistics
        """
        async with self._lock:
            current_time = time.time()
            start_time = current_time - window_seconds
            
            # Collect metrics in window
            latencies = []
            total_tokens = 0
            error_count = 0
            provider_counts = defaultdict(int)
            model_counts = defaultdict(int)
            error_counts = defaultdict(int)
            
            for timestamp, metric in self._metrics:
                if timestamp < start_time:
                    continue
                
                if provider and self._extract_provider(metric.model) != provider:
                    continue
                
                latencies.append(metric.latency_ms)
                total_tokens += (metric.input_tokens + metric.output_tokens)
                
                if metric.error_class:
                    error_count += 1
                    error_counts[metric.error_class] += 1
                
                metric_provider = self._extract_provider(metric.model)
                provider_counts[metric_provider] += 1
                model_counts[metric.model] += 1
            
            # Calculate statistics
            summary = MetricsSummary()
            summary.count = len(latencies)
            
            if latencies:
                summary.avg_latency_ms = statistics.mean(latencies)
                summary.p50_latency_ms = statistics.median(latencies)
                
                if len(latencies) >= 20:
                    sorted_latencies = sorted(latencies)
                    summary.p95_latency_ms = sorted_latencies[int(len(latencies) * 0.95)]
                    summary.p99_latency_ms = sorted_latencies[int(len(latencies) * 0.99)]
                
                summary.error_rate = error_count / len(latencies)
            
            summary.total_tokens = total_tokens
            summary.providers = dict(provider_counts)
            summary.models = dict(model_counts)
            summary.errors = dict(error_counts)
            
            return summary
    
    async def get_percentile(
        self,
        percentile: float,
        metric: str = "latency_ms",
        window_seconds: float = 300
    ) -> float:
        """
        Get percentile value for a metric.
        
        Args:
            percentile: Percentile (0-100)
            metric: Metric name (latency_ms, tokens, etc.)
            window_seconds: Time window
            
        Returns:
            Percentile value
        """
        async with self._lock:
            current_time = time.time()
            start_time = current_time - window_seconds
            
            values = []
            for timestamp, m in self._metrics:
                if timestamp < start_time:
                    continue
                
                if metric == "latency_ms":
                    values.append(m.latency_ms)
                elif metric == "tokens":
                    values.append(m.input_tokens + m.output_tokens)
                elif metric == "input_tokens":
                    values.append(m.input_tokens)
                elif metric == "output_tokens":
                    values.append(m.output_tokens)
            
            if not values:
                return 0.0
            
            sorted_values = sorted(values)
            index = int(len(sorted_values) * (percentile / 100))
            return sorted_values[min(index, len(sorted_values) - 1)]
    
    async def clear(self) -> None:
        """Clear all stored metrics."""
        async with self._lock:
            self._metrics.clear()
            self._by_provider.clear()
            self._by_model.clear()
            self._by_request.clear()
            self._total_requests = 0
            self._total_errors = 0
            self._total_tokens = 0
            self._total_latency_ms = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics (synchronous for convenience)."""
        return {
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "total_tokens": self._total_tokens,
            "avg_latency_ms": self._total_latency_ms / self._total_requests if self._total_requests > 0 else 0,
            "error_rate": self._total_errors / self._total_requests if self._total_requests > 0 else 0,
            "stored_metrics": len(self._metrics),
            "unique_models": len(self._by_model),
            "unique_providers": len(self._by_provider)
        }
    
    # Private methods
    
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
    
    async def _cleanup_old_metrics(self, current_time: float) -> None:
        """Remove metrics older than TTL."""
        cutoff_time = current_time - self.ttl_seconds
        
        # Clean up by-provider index
        for provider, metrics_list in list(self._by_provider.items()):
            self._by_provider[provider] = [
                m for m in metrics_list 
                if self._get_metric_time(m) > cutoff_time
            ]
            if not self._by_provider[provider]:
                del self._by_provider[provider]
        
        # Clean up by-model index
        for model, metrics_list in list(self._by_model.items()):
            self._by_model[model] = [
                m for m in metrics_list
                if self._get_metric_time(m) > cutoff_time
            ]
            if not self._by_model[model]:
                del self._by_model[model]
        
        # Clean up by-request index
        for request_id, metric in list(self._by_request.items()):
            if self._get_metric_time(metric) <= cutoff_time:
                del self._by_request[request_id]
    
    def _get_metric_time(self, metric: AgentMetrics) -> float:
        """Get timestamp for a metric (would be stored with metric in real implementation)."""
        # For now, return current time minus a portion of TTL
        return time.time() - (self.ttl_seconds * 0.1)


from typing import Tuple