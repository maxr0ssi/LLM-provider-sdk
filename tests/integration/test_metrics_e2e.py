"""End-to-end integration tests for metrics collection."""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock

from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.observability import MetricsConfig
from steer_llm_sdk.observability.sinks import InMemoryMetricsSink
from steer_llm_sdk.models.generation import GenerationResponse


@pytest.mark.skip(reason="SteerLLMClient monkeypatch does not prevent MetricsCollector batch processor from starting outside event loop")
class TestMetricsE2E:
    """Test metrics collection end-to-end with the client."""
    
    @pytest.fixture
    def mock_router(self, monkeypatch):
        """Mock the router to avoid real API calls."""
        mock = AsyncMock()
        
        # Mock generate response
        mock.generate.return_value = GenerationResponse(
            text="Hello, world!",
            model="gpt-4o-mini",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30, "cached_tokens": 0},
            provider="openai"
        )
        
        # Mock streaming response
        async def mock_stream(*args, **kwargs):
            # Yield chunks with usage
            yield ("Hello", None)
            yield (", ", None)
            yield ("world", None)
            yield ("!", {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14})
        
        mock.generate_stream = mock_stream
        
        # Patch the router in client
        def mock_init(self, *args, **kwargs):
            self.router = mock
            self.metrics_collector = getattr(self, 'metrics_collector', None)
        
        monkeypatch.setattr(
            "steer_llm_sdk.api.client.SteerLLMClient.__init__",
            mock_init
        )
        
        return mock
    
    @pytest.mark.asyncio
    async def test_generate_metrics(self, mock_router, monkeypatch):
        """Test metrics collection for generate calls."""
        # Create sink
        sink = InMemoryMetricsSink()
        
        # Create client with metrics
        client = SteerLLMClient(
            metrics_config=MetricsConfig(enabled=True),
            metrics_sinks=[sink]
        )
        
        # Need to properly initialize the client
        client.router = mock_router
        
        # Mock get_config to return provider info
        mock_config = MagicMock()
        mock_config.provider.value = "openai"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 100
        monkeypatch.setattr(
            "steer_llm_sdk.api.client.get_config",
            lambda x: mock_config
        )
        
        # Make a generate call
        response = await client.generate(
            messages="Hello!",
            model="gpt-4"
        )
        
        assert response.text == "Hello, world!"
        
        # Check metrics were recorded
        await asyncio.sleep(0.1)  # Give time for async recording
        metrics = await sink.get_metrics()
        
        assert len(metrics) == 1
        metric = metrics[0]
        
        assert metric.model == "gpt-4"
        assert metric.input_tokens == 10
        assert metric.output_tokens == 20
        assert metric.latency_ms > 0
        assert metric.error_class is None
    
    @pytest.mark.asyncio
    async def test_streaming_metrics(self, mock_router, monkeypatch):
        """Test metrics collection for streaming calls."""
        # Create sink
        sink = InMemoryMetricsSink()
        
        # Create client with metrics
        client = SteerLLMClient(
            metrics_config=MetricsConfig(enabled=True),
            metrics_sinks=[sink]
        )
        client.router = mock_router
        
        # Mock get_config
        mock_config = MagicMock()
        mock_config.provider.value = "anthropic"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 100
        monkeypatch.setattr(
            "steer_llm_sdk.api.client.get_config",
            lambda x: mock_config
        )
        
        # Make a streaming call
        response = await client.stream_with_usage(
            messages="Hello!",
            model="claude-3"
        )
        
        assert response.get_text() == "Hello, world!"
        
        # Check metrics
        await asyncio.sleep(0.1)
        metrics = await sink.get_metrics()
        
        assert len(metrics) == 1
        metric = metrics[0]
        
        assert metric.model == "claude-3"
        assert metric.input_tokens == 10
        assert metric.output_tokens == 4
        assert metric.latency_ms > 0
    
    @pytest.mark.asyncio
    async def test_error_metrics(self, mock_router, monkeypatch):
        """Test metrics collection when errors occur."""
        # Create sink
        sink = InMemoryMetricsSink()
        
        # Create client
        client = SteerLLMClient(
            metrics_config=MetricsConfig(enabled=True),
            metrics_sinks=[sink]
        )
        client.router = mock_router
        
        # Mock config
        mock_config = MagicMock()
        mock_config.provider.value = "xai"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 100
        monkeypatch.setattr(
            "steer_llm_sdk.api.client.get_config",
            lambda x: mock_config
        )
        
        # Make generate fail
        mock_router.generate.side_effect = ValueError("API Error")
        
        # Call should raise
        with pytest.raises(ValueError):
            await client.generate("Hello!", model="grok-1")
        
        # Check error was recorded
        await asyncio.sleep(0.1)
        metrics = await sink.get_metrics()
        
        assert len(metrics) == 1
        assert metrics[0].error_class == "ValueError"
    
    @pytest.mark.asyncio
    async def test_streaming_with_callbacks(self, mock_router, monkeypatch):
        """Test metrics with streaming callbacks."""
        sink = InMemoryMetricsSink()
        
        client = SteerLLMClient(
            metrics_config=MetricsConfig(enabled=True),
            metrics_sinks=[sink]
        )
        client.router = mock_router
        
        # Mock config
        mock_config = MagicMock()
        mock_config.provider.value = "openai"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 100
        monkeypatch.setattr(
            "steer_llm_sdk.api.client.get_config",
            lambda x: mock_config
        )
        
        # Track events
        events = []
        
        async def on_start(event):
            events.append(("start", event))
        
        async def on_delta(event):
            events.append(("delta", event))
        
        async def on_complete(event):
            events.append(("complete", event))
        
        # Stream with callbacks
        response = await client.stream_with_usage(
            messages="Test",
            model="gpt-4",
            on_start=on_start,
            on_delta=on_delta,
            on_complete=on_complete
        )
        
        # Should have events
        assert any(e[0] == "start" for e in events)
        assert any(e[0] == "delta" for e in events)
        assert any(e[0] == "complete" for e in events)
        
        # And metrics
        await asyncio.sleep(0.1)
        metrics = await sink.get_metrics()
        assert len(metrics) == 1
    
    @pytest.mark.asyncio
    async def test_disabled_metrics(self, mock_router, monkeypatch):
        """Test that disabled metrics don't collect."""
        sink = InMemoryMetricsSink()
        
        # Create client with disabled metrics
        client = SteerLLMClient(
            metrics_config=MetricsConfig(enabled=False),
            metrics_sinks=[sink]
        )
        client.router = mock_router
        
        # Mock config
        mock_config = MagicMock()
        mock_config.provider.value = "openai"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 100
        monkeypatch.setattr(
            "steer_llm_sdk.api.client.get_config",
            lambda x: mock_config
        )
        
        # Make calls
        await client.generate("Hello!", model="gpt-4")
        
        # Should not record
        await asyncio.sleep(0.1)
        assert len(await sink.get_metrics()) == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_metrics(self, mock_router, monkeypatch):
        """Test metrics with concurrent requests."""
        sink = InMemoryMetricsSink()
        
        client = SteerLLMClient(
            metrics_config=MetricsConfig(enabled=True),
            metrics_sinks=[sink]
        )
        client.router = mock_router
        
        # Mock config
        mock_config = MagicMock()
        mock_config.provider.value = "openai"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 100
        monkeypatch.setattr(
            "steer_llm_sdk.api.client.get_config",
            lambda x: mock_config
        )
        
        # Make concurrent requests
        tasks = []
        for i in range(5):
            task = client.generate(f"Hello {i}!", model=f"gpt-{i % 2 + 3}")
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # Should have all metrics
        await asyncio.sleep(0.1)
        metrics = await sink.get_metrics()
        assert len(metrics) == 5
        
        # Check summary
        summary = await sink.get_summary()
        assert summary.count == 5
        assert summary.total_tokens == 150  # 5 * 30