"""
Streaming configuration models.

This module provides configuration options for streaming behavior,
including JSON handling, event processing, and performance tuning.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, Awaitable


@dataclass
class StreamingOptions:
    """
    Configuration for streaming behavior.
    
    This class consolidates all streaming-related options to avoid
    parameter sprawl and provide a clean API for streaming configuration.
    """
    
    # JSON handling
    enable_json_stream_handler: bool = False
    """Enable JSON stream handler for response_format=json_object."""
    
    # Usage tracking
    enable_usage_aggregation: bool = True
    """Enable usage aggregation for providers without streaming usage."""
    
    aggregator_type: str = "auto"
    """Type of aggregator to use: 'auto', 'tiktoken', 'character'."""
    
    prefer_tiktoken: bool = True
    """Prefer tiktoken for OpenAI models when available."""
    
    # Event processing
    enable_event_processor: bool = False
    """Enable event processor for filtering and transformation."""
    
    event_callbacks: Optional[Dict[str, Callable[[Any], Awaitable[None]]]] = None
    """Event callbacks for streaming events (on_start, on_delta, etc.)."""
    
    event_processor: Optional[Any] = None
    """Custom event processor instance."""
    
    # Performance metrics
    measure_ttft: bool = True
    """Measure Time To First Token (TTFT)."""
    
    measure_inter_token_latency: bool = False
    """Measure latency between tokens."""
    
    # Event batching
    batch_events: bool = True
    """Enable event batching for performance."""
    
    batch_size: int = 10
    """Number of events to batch before processing."""
    
    batch_timeout: float = 0.1
    """Timeout in seconds for event batching."""
    
    # Rate limiting
    enable_rate_limiting: bool = False
    """Enable rate limiting for event processing."""
    
    max_events_per_second: int = 1000
    """Maximum events to process per second."""
    
    # Debugging
    log_streaming_metrics: bool = False
    """Log streaming metrics for debugging."""
    
    capture_raw_events: bool = False
    """Capture raw provider events for debugging."""
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.event_callbacks is None:
            self.event_callbacks = {}
            
        # Validate batch settings
        if self.batch_size < 1:
            self.batch_size = 1
        if self.batch_timeout < 0:
            self.batch_timeout = 0.1
            
        # Validate rate limiting
        if self.max_events_per_second < 1:
            self.max_events_per_second = 1000
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "StreamingOptions":
        """Create StreamingOptions from dictionary.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            StreamingOptions instance
        """
        # Filter out unknown keys
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_config = {k: v for k, v in config.items() if k in known_fields}
        return cls(**filtered_config)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.
        
        Returns:
            Configuration as dictionary
        """
        return {
            "enable_json_stream_handler": self.enable_json_stream_handler,
            "enable_usage_aggregation": self.enable_usage_aggregation,
            "enable_event_processor": self.enable_event_processor,
            "event_callbacks": list(self.event_callbacks.keys()) if self.event_callbacks else [],
            "measure_ttft": self.measure_ttft,
            "measure_inter_token_latency": self.measure_inter_token_latency,
            "batch_events": self.batch_events,
            "batch_size": self.batch_size,
            "batch_timeout": self.batch_timeout,
            "enable_rate_limiting": self.enable_rate_limiting,
            "max_events_per_second": self.max_events_per_second,
            "log_streaming_metrics": self.log_streaming_metrics,
            "capture_raw_events": self.capture_raw_events,
        }


# Preset configurations for common use cases

DEFAULT_OPTIONS = StreamingOptions()
"""Default streaming options with minimal overhead."""

JSON_MODE_OPTIONS = StreamingOptions(
    enable_json_stream_handler=True,
    log_streaming_metrics=True
)
"""Options optimized for JSON response format."""

DEBUG_OPTIONS = StreamingOptions(
    enable_json_stream_handler=True,
    enable_event_processor=True,
    measure_ttft=True,
    measure_inter_token_latency=True,
    log_streaming_metrics=True,
    capture_raw_events=True,
    batch_events=False  # Disable batching for immediate debugging
)
"""Options for debugging with full metrics and logging."""

HIGH_PERFORMANCE_OPTIONS = StreamingOptions(
    enable_json_stream_handler=False,
    enable_usage_aggregation=False,
    enable_event_processor=False,
    measure_ttft=False,
    batch_events=True,
    batch_size=50,
    batch_timeout=0.05
)
"""Options optimized for high-throughput streaming."""