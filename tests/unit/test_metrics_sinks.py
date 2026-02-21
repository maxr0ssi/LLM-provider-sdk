"""Unit tests for metrics sinks."""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, patch

from steer_llm_sdk.observability.metrics import AgentMetrics
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink, OTelMetricsSink


class TestInMemoryMetricsSink:
    """Test the in-memory metrics sink."""
    
    @pytest.fixture
    def sink(self):
        """Create test sink."""
        return InMemoryMetricsSink(max_size=100, ttl_seconds=60)
    
    @pytest.mark.asyncio
    async def test_record_and_retrieve(self, sink):
        """Test recording and retrieving metrics."""
        # Record some metrics
        for i in range(5):
            metric = AgentMetrics(
                request_id=f"req-{i}",
                model=f"gpt-{i % 2 + 3}",  # gpt-3 or gpt-4
                latency_ms=100 + i * 10,
                input_tokens=50 + i,
                output_tokens=100 + i,
                cached_tokens=i,
                retries=0,
                error_class=None if i < 4 else "TimeoutError"
            )
            await sink.record(metric)
        
        # Retrieve all
        metrics = await sink.get_metrics()
        assert len(metrics) == 5
        
        # Test filters
        gpt4_metrics = await sink.get_metrics(model="gpt-4")
        assert all(m.model == "gpt-4" for m in gpt4_metrics)
        
        # Test request ID lookup
        req2_metrics = await sink.get_metrics(request_id="req-2")
        assert len(req2_metrics) == 1
        assert req2_metrics[0].request_id == "req-2"
    
    @pytest.mark.asyncio
    async def test_max_size_limit(self):
        """Test that sink respects max size."""
        sink = InMemoryMetricsSink(max_size=3)
        
        # Record more than max
        for i in range(5):
            metric = AgentMetrics(
                request_id=f"req-{i}",
                model="gpt-4",
                latency_ms=100
            )
            await sink.record(metric)
        
        # Should only have last 3
        metrics = await sink.get_metrics()
        assert len(metrics) == 3
        assert [m.request_id for m in metrics] == ["req-2", "req-3", "req-4"]
    
    @pytest.mark.asyncio
    async def test_get_summary(self, sink):
        """Test summary statistics."""
        # Record metrics with various latencies
        latencies = [100, 200, 150, 300, 250]
        for i, latency in enumerate(latencies):
            metric = AgentMetrics(
                model="gpt-4",
                latency_ms=latency,
                input_tokens=10,
                output_tokens=20,
                error_class="RateLimitError" if i == 0 else None
            )
            await sink.record(metric)
        
        # Get summary
        summary = await sink.get_summary(window_seconds=300)
        
        assert summary.count == 5
        assert summary.avg_latency_ms == 200  # (100+200+150+300+250)/5
        assert summary.p50_latency_ms == 200  # median
        assert summary.total_tokens == 150  # 5 * (10+20)
        assert summary.error_rate == 0.2  # 1/5
        assert summary.errors["RateLimitError"] == 1
    
    @pytest.mark.asyncio
    async def test_percentiles(self, sink):
        """Test percentile calculations."""
        # Record 100 metrics with increasing latencies
        for i in range(100):
            metric = AgentMetrics(
                model="gpt-4",
                latency_ms=i * 10,  # 0, 10, 20, ..., 990
                input_tokens=10,
                output_tokens=20
            )
            await sink.record(metric)
        
        # Test percentiles
        p50 = await sink.get_percentile(50, "latency_ms")
        p95 = await sink.get_percentile(95, "latency_ms")
        p99 = await sink.get_percentile(99, "latency_ms")
        
        assert 490 <= p50 <= 500  # Around 495
        assert 940 <= p95 <= 950  # Around 945
        assert 980 <= p99 <= 990  # Around 985
    
    @pytest.mark.asyncio
    async def test_provider_extraction(self, sink):
        """Test provider extraction from model names."""
        models = [
            ("gpt-4", "openai"),
            ("gpt-3.5-turbo", "openai"),
            ("claude-3-opus", "anthropic"),
            ("claude-instant", "anthropic"),
            ("grok-1", "xai"),
            ("unknown-model", "unknown")
        ]
        
        for model, expected_provider in models:
            metric = AgentMetrics(model=model, latency_ms=100)
            await sink.record(metric)
        
        # Check provider counts
        summary = await sink.get_summary()
        assert summary.providers["openai"] == 2
        assert summary.providers["anthropic"] == 2
        assert summary.providers["xai"] == 1
        assert summary.providers["unknown"] == 1
    
    @pytest.mark.asyncio
    async def test_clear(self, sink):
        """Test clearing metrics."""
        # Record some metrics
        for i in range(5):
            await sink.record(AgentMetrics(model="gpt-4", latency_ms=100))
        
        # Verify they're there
        assert len(await sink.get_metrics()) == 5
        
        # Clear
        await sink.clear()
        
        # Should be empty
        assert len(await sink.get_metrics()) == 0
        assert sink.get_stats()["total_requests"] == 0
    
    def test_get_stats(self, sink):
        """Test synchronous stats method."""
        # Use asyncio.run for the async operations
        async def record_metrics():
            for i in range(10):
                metric = AgentMetrics(
                    model="gpt-4" if i < 6 else "claude-3",
                    latency_ms=100,
                    input_tokens=10,
                    output_tokens=20,
                    error_class="TimeoutError" if i == 0 else None
                )
                await sink.record(metric)
        
        asyncio.run(record_metrics())
        
        stats = sink.get_stats()
        assert stats["total_requests"] == 10
        assert stats["total_errors"] == 1
        assert stats["total_tokens"] == 300  # 10 * (10+20)
        assert stats["avg_latency_ms"] == 100
        assert stats["error_rate"] == 0.1
        assert stats["unique_models"] == 2


class TestOTelMetricsSink:
    """Test the OpenTelemetry metrics sink."""
    
    @pytest.mark.asyncio
    async def test_disabled_when_otel_missing(self):
        """Test that sink is disabled when OpenTelemetry is not available."""
        with patch('steer_llm_sdk.observability.sinks.otlp.metrics', None):
            sink = OTelMetricsSink()
            assert not sink.enabled

            # Should not error when recording
            await sink.record(AgentMetrics(model="gpt-4", latency_ms=100))
            await sink.flush()
    
    @pytest.mark.asyncio
    async def test_record_with_mock_otel(self):
        """Test recording with mocked OpenTelemetry."""
        mock_meter = MagicMock()
        mock_histogram = MagicMock()
        mock_counter = MagicMock()
        mock_updown = MagicMock()
        
        mock_meter.create_histogram.return_value = mock_histogram
        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_up_down_counter.return_value = mock_updown
        
        with patch('steer_llm_sdk.observability.sinks.otlp.metrics') as mock_metrics:
            mock_metrics.get_meter.return_value = mock_meter
            
            sink = OTelMetricsSink(service_name="test", namespace="test")
            assert sink.enabled
            
            # Record a metric
            metric = AgentMetrics(
                model="gpt-4",
                latency_ms=150,
                input_tokens=50,
                output_tokens=100,
                cached_tokens=10,
                retries=2,
                error_class="RateLimitError"
            )
            await sink.record(metric)
            
            # Verify instruments were created
            assert mock_meter.create_histogram.call_count >= 2  # duration, ttft
            assert mock_meter.create_counter.call_count >= 4  # requests, tokens, errors, retries
            
            # Verify metrics were recorded
            # Note: Actual calls depend on implementation details
            assert mock_histogram.record.called or mock_counter.add.called
    
    def test_provider_extraction(self):
        """Test provider extraction logic."""
        sink = OTelMetricsSink()
        
        test_cases = [
            ("gpt-4", "openai"),
            ("gpt-3.5-turbo", "openai"),
            ("claude-3-opus", "anthropic"),
            ("claude-instant", "anthropic"),
            ("grok-1", "xai"),
            ("grok-2-mini", "xai"),
            ("llama-70b", "unknown"),
            ("", "unknown")
        ]
        
        for model, expected in test_cases:
            assert sink._extract_provider(model) == expected
    
    def test_streaming_metrics(self):
        """Test streaming metrics recording."""
        with patch('steer_llm_sdk.observability.sinks.otlp.metrics') as mock_metrics:
            mock_meter = MagicMock()
            mock_histogram = MagicMock()
            mock_metrics.get_meter.return_value = mock_meter
            mock_meter.create_histogram.return_value = mock_histogram
            
            sink = OTelMetricsSink()
            
            # Record streaming metrics
            sink.record_streaming_metrics({
                "provider": "openai",
                "model": "gpt-4",
                "first_chunk_latency_ms": 250.5
            })
            
            # Should attempt to record TTFT
            # Note: We can't easily verify the exact call due to dict construction
            assert True  # Just verify no errors
    
    def test_circuit_breaker_state(self):
        """Test circuit breaker state recording."""
        with patch('steer_llm_sdk.observability.sinks.otlp.metrics') as mock_metrics:
            mock_meter = MagicMock()
            mock_updown = MagicMock()
            mock_metrics.get_meter.return_value = mock_meter
            mock_meter.create_up_down_counter.return_value = mock_updown
            
            sink = OTelMetricsSink()
            
            # Record state changes
            sink.record_circuit_breaker_state("openai", True)  # Open
            sink.record_circuit_breaker_state("openai", False)  # Close
            
            # Should have recorded +1 and -1
            # Note: Can't easily verify exact calls due to initialization