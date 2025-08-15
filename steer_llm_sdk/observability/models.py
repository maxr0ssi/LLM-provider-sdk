"""
Enhanced metrics models for comprehensive observability.

This module defines data models for collecting metrics across the SDK,
including request, streaming, reliability, and usage metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import time


class MetricType(str, Enum):
    """Types of metrics that can be collected."""
    REQUEST = "request"
    STREAMING = "streaming"
    RELIABILITY = "reliability"
    USAGE = "usage"
    ERROR = "error"


@dataclass
class BaseMetrics:
    """Base class for all metrics."""
    timestamp: float = field(default_factory=time.time)
    metric_type: MetricType = MetricType.REQUEST
    provider: Optional[str] = None
    model: Optional[str] = None
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary format."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class RequestMetrics(BaseMetrics):
    """Metrics for a single request."""
    metric_type: MetricType = field(default=MetricType.REQUEST, init=False)
    
    # Timing
    duration_ms: Optional[float] = None
    time_to_first_token_ms: Optional[float] = None
    
    # Usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    
    # Cost (optional)
    estimated_cost: Optional[float] = None
    
    # Request details
    method: Optional[str] = None  # generate, stream, etc.
    response_format: Optional[str] = None  # text, json_object, etc.
    
    # Performance
    queue_time_ms: Optional[float] = None
    provider_latency_ms: Optional[float] = None


@dataclass
class StreamingMetrics(BaseMetrics):
    """Metrics for streaming operations."""
    metric_type: MetricType = field(default=MetricType.STREAMING, init=False)
    
    # Chunk metrics
    total_chunks: int = 0
    total_chars: int = 0
    chunks_per_second: float = 0.0
    chars_per_second: float = 0.0
    
    # Timing
    streaming_duration_ms: float = 0.0
    first_chunk_latency_ms: Optional[float] = None
    
    # JSON streaming (if applicable)
    json_objects_found: int = 0
    json_parse_errors: int = 0
    
    # Aggregation
    aggregation_method: Optional[str] = None  # tiktoken, character, etc.
    aggregation_confidence: Optional[float] = None


@dataclass
class ReliabilityMetrics(BaseMetrics):
    """Metrics for reliability features."""
    metric_type: MetricType = field(default=MetricType.RELIABILITY, init=False)
    
    # Retry metrics
    retry_attempts: int = 0
    retry_succeeded: bool = False
    total_retry_delay_ms: float = 0.0
    
    # Circuit breaker
    circuit_breaker_state: Optional[str] = None  # CLOSED, OPEN, HALF_OPEN
    circuit_breaker_failures: int = 0
    
    # Error details
    error_type: Optional[str] = None
    error_category: Optional[str] = None  # rate_limit, auth, etc.
    is_retryable: bool = False


@dataclass
class UsageMetrics(BaseMetrics):
    """Aggregated usage metrics over time."""
    metric_type: MetricType = field(default=MetricType.USAGE, init=False)
    
    # Time window
    window_start: float = field(default_factory=time.time)
    window_duration_seconds: float = 60.0  # Default 1 minute
    
    # Aggregated counts
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Token usage
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cached_tokens: int = 0
    
    # Cost
    total_estimated_cost: float = 0.0
    
    # Provider distribution
    requests_by_provider: Dict[str, int] = field(default_factory=dict)
    tokens_by_provider: Dict[str, int] = field(default_factory=dict)
    
    # Error distribution
    errors_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class ErrorMetrics(BaseMetrics):
    """Detailed error metrics."""
    metric_type: MetricType = field(default=MetricType.ERROR, init=False)
    
    error_type: str = ""
    error_message: str = ""
    error_category: Optional[str] = None
    is_retryable: bool = False
    
    # Context
    retry_attempt: int = 0
    circuit_breaker_open: bool = False
    
    # Stack trace (optional, for debugging)
    stack_trace: Optional[str] = None


@dataclass
class AgentMetrics:
    """Legacy agent metrics for backward compatibility."""
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
    
    @classmethod
    def from_request_metrics(cls, metrics: RequestMetrics) -> AgentMetrics:
        """Create AgentMetrics from RequestMetrics for compatibility."""
        return cls(
            request_id=metrics.request_id,
            model=metrics.model or "",
            latency_ms=int(metrics.duration_ms or 0),
            input_tokens=metrics.prompt_tokens,
            output_tokens=metrics.completion_tokens,
            cached_tokens=metrics.cached_tokens,
            retries=0,  # Would come from ReliabilityMetrics
            error_class=None,
            tools_used=[]
        )


@dataclass
class MetricsBatch:
    """Batch of metrics for efficient processing."""
    metrics: List[BaseMetrics] = field(default_factory=list)
    batch_id: str = ""
    created_at: float = field(default_factory=time.time)
    
    def add(self, metric: BaseMetrics) -> None:
        """Add a metric to the batch."""
        self.metrics.append(metric)
    
    def size(self) -> int:
        """Get the number of metrics in the batch."""
        return len(self.metrics)
    
    def clear(self) -> None:
        """Clear all metrics from the batch."""
        self.metrics.clear()