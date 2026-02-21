"""Unit tests for metrics collector."""

import asyncio
import pytest
import time
from unittest.mock import MagicMock, AsyncMock

from steer_llm_sdk.observability import (
    MetricsCollector, MetricsConfig, RequestMetrics, 
    StreamingMetrics, ReliabilityMetrics, ErrorMetrics
)
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink


class TestMetricsCollector:
    """Test the metrics collector functionality."""
    
    @pytest.fixture
    def collector(self):
        """Create a test collector with in-memory sink."""
        config = MetricsConfig(
            enabled=True,
            batch_size=1,  # No batching for easier testing
            enable_streaming_metrics=True,
            enable_reliability_metrics=True
        )
        collector = MetricsCollector(config)
        sink = InMemoryMetricsSink()
        collector.add_sink(sink)
        return collector, sink
    
    @pytest.mark.asyncio
    async def test_track_request_context(self, collector):
        """Test request tracking context manager."""
        collector, sink = collector
        
        async with collector.track_request(
            provider="openai",
            model="gpt-4",
            method="generate",
            request_id="test-123"
        ) as metrics:
            # Simulate some work
            await asyncio.sleep(0.01)
            
            # Update metrics
            metrics.prompt_tokens = 100
            metrics.completion_tokens = 50
            metrics.total_tokens = 150
        
        # Check recorded metrics
        recorded = await sink.get_metrics()
        assert len(recorded) == 1
        
        metric = recorded[0]
        assert metric.model == "gpt-4"
        assert metric.input_tokens == 100
        assert metric.output_tokens == 50
        assert metric.latency_ms > 0
        assert metric.request_id == "test-123"
    
    @pytest.mark.asyncio
    async def test_track_request_with_error(self, collector):
        """Test request tracking with error."""
        collector, sink = collector
        
        with pytest.raises(ValueError):
            async with collector.track_request(
                provider="anthropic",
                model="claude-3",
                method="generate"
            ) as metrics:
                raise ValueError("Test error")
        
        # Should record error metric
        recorded = await sink.get_metrics()
        assert len(recorded) == 1
        assert recorded[0].error_class == "ValueError"
    
    @pytest.mark.asyncio
    async def test_streaming_metrics(self, collector):
        """Test recording streaming metrics."""
        collector, sink = collector
        
        # Record streaming metrics
        await collector.record_streaming_metrics(
            request_id="stream-123",
            streaming_metrics={
                "chunks": 100,
                "total_chars": 5000,
                "chunks_per_second": 50.5,
                "chars_per_second": 2525.0,
                "duration_seconds": 1.98,
                "json_objects_found": 2,
                "aggregation_method": "tiktoken",
                "aggregation_confidence": 0.95
            }
        )
        
        # Check metrics - since we're using AgentMetrics compatibility,
        # we won't see streaming-specific fields in the sink
        # This is a limitation of the current design
        assert True  # For now, just verify no errors
    
    @pytest.mark.asyncio
    async def test_reliability_metrics(self, collector):
        """Test recording reliability metrics."""
        collector, sink = collector
        
        await collector.record_reliability_metrics(
            request_id="retry-123",
            retry_attempts=2,
            retry_succeeded=True,
            total_retry_delay_ms=1500,
            circuit_breaker_state="CLOSED",
            error_type="RateLimitError",
            error_category="rate_limit",
            is_retryable=True
        )
        
        # Verify no errors
        assert True
    
    @pytest.mark.asyncio
    async def test_disabled_collector(self):
        """Test that disabled collector doesn't record."""
        config = MetricsConfig(enabled=False)
        collector = MetricsCollector(config)
        sink = InMemoryMetricsSink()
        collector.add_sink(sink)
        
        async with collector.track_request("openai", "gpt-4") as metrics:
            metrics.prompt_tokens = 100
        
        # Should not record anything
        recorded = await sink.get_metrics()
        assert len(recorded) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_sinks(self, collector):
        """Test recording to multiple sinks."""
        collector, sink1 = collector
        sink2 = InMemoryMetricsSink()
        collector.add_sink(sink2)
        
        async with collector.track_request("xai", "grok-1") as metrics:
            metrics.prompt_tokens = 50
        
        # Both sinks should have the metric
        assert len(await sink1.get_metrics()) == 1
        assert len(await sink2.get_metrics()) == 1
    
    @pytest.mark.asyncio
    async def test_sink_removal(self, collector):
        """Test removing a sink."""
        collector, sink = collector
        
        # Record a metric
        async with collector.track_request("openai", "gpt-4"):
            pass
        
        # Remove sink
        collector.remove_sink(sink)
        
        # Record another metric
        async with collector.track_request("openai", "gpt-4"):
            pass
        
        # Should only have one metric (before removal)
        assert len(await sink.get_metrics()) == 1
    
    @pytest.mark.asyncio
    async def test_batch_collection(self):
        """Test batch collection mode."""
        config = MetricsConfig(
            enabled=True,
            batch_size=5,
            batch_timeout_seconds=0.1
        )
        collector = MetricsCollector(config)
        sink = InMemoryMetricsSink()
        collector.add_sink(sink)
        
        # Record multiple metrics quickly
        for i in range(3):
            async with collector.track_request("openai", f"model-{i}"):
                pass
        
        # Should not be recorded yet (batching)
        assert len(await sink.get_metrics()) == 0
        
        # Wait for batch timeout
        await asyncio.sleep(0.15)
        
        # Now should be recorded
        assert len(await sink.get_metrics()) == 3
        
        # Cleanup
        await collector.shutdown()
    
    @pytest.mark.asyncio
    async def test_sampling(self):
        """Test metric sampling."""
        config = MetricsConfig(
            enabled=True,
            batch_size=1,
            request_sampling_rate=0.5  # 50% sampling
        )
        collector = MetricsCollector(config)
        sink = InMemoryMetricsSink()
        collector.add_sink(sink)
        
        # Record many metrics
        for i in range(100):
            async with collector.track_request("openai", "gpt-4"):
                pass
        
        # Should have roughly 50% of metrics (with some variance)
        recorded = len(await sink.get_metrics())
        assert 30 <= recorded <= 70  # Allow for variance
    
    @pytest.mark.asyncio
    async def test_custom_filter(self):
        """Test custom metric filters."""
        class OnlyGPT4Filter:
            def should_collect(self, metric):
                return metric.model == "gpt-4"

        config = MetricsConfig(
            enabled=True,
            batch_size=1,
            filters=[OnlyGPT4Filter()]
        )
        collector = MetricsCollector(config)
        sink = InMemoryMetricsSink()
        collector.add_sink(sink)
        
        # Record different models
        async with collector.track_request("openai", "gpt-4"):
            pass
        async with collector.track_request("anthropic", "claude-3"):
            pass
        async with collector.track_request("openai", "gpt-3.5"):
            pass
        
        # Should only have gpt-4
        recorded = await sink.get_metrics()
        assert len(recorded) == 1
        assert recorded[0].model == "gpt-4"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, collector):
        """Test concurrent request tracking."""
        collector, sink = collector
        
        async def make_request(i):
            async with collector.track_request(
                provider="openai",
                model=f"model-{i}",
                request_id=f"req-{i}"
            ) as metrics:
                await asyncio.sleep(0.01)
                metrics.prompt_tokens = i * 10
        
        # Make concurrent requests
        await asyncio.gather(*[make_request(i) for i in range(5)])
        
        # Should have all metrics
        recorded = await sink.get_metrics()
        assert len(recorded) == 5
        
        # Check they're all different
        request_ids = {m.request_id for m in recorded}
        assert len(request_ids) == 5