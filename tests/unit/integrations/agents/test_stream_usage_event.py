"""Test that AgentRunner.stream() yields a final usage StreamEvent."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from steer_llm_sdk.agents.runner.agent_runner import AgentRunner
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition
from steer_llm_sdk.agents.models.agent_options import AgentOptions
from steer_llm_sdk.agents.models.stream_event import StreamEvent
from steer_llm_sdk.models.events import StreamCompleteEvent


@pytest.fixture
def definition():
    return AgentDefinition(
        model="gpt-4o-mini",
        system="You are a test assistant.",
        user_template="{query}",
    )


@pytest.fixture
def opts():
    return AgentOptions(
        runtime="openai-agents",
        streaming=True,
        metadata={},
    )


class FakeRuntime:
    """Minimal runtime that emits text deltas then completes with usage."""

    async def prepare(self, definition, run_options):
        return {"prepared": True}

    async def run_stream(self, prepared, variables, events):
        # Emit a couple of text deltas via on_delta
        await events.on_delta("Hello ")
        await events.on_delta("world!")

        # Build a StreamCompleteEvent with usage data
        complete_event = StreamCompleteEvent(
            total_chunks=2,
            duration_ms=150.0,
            final_usage={
                "prompt_tokens": 50,
                "completion_tokens": 120,
                "total_tokens": 170,
            },
        )
        complete_event.metadata = {
            "cost_usd": 0.0042,
            "tools_used": ["search"],
        }

        await events.on_complete(complete_event)
        # Yield nothing — events are pushed via callbacks
        return
        yield  # make it an async generator


@pytest.mark.asyncio
async def test_stream_yields_usage_event_last(definition, opts):
    """stream() must yield a usage StreamEvent as the very last item."""
    runner = AgentRunner()

    fake_runtime = FakeRuntime()
    with patch(
        "steer_llm_sdk.agents.runner.agent_runner.get_agent_runtime",
        return_value=fake_runtime,
    ):
        events = []
        async for ev in runner.stream(definition, {"query": "hi"}, opts):
            events.append(ev)

    # Should have text events + one usage event
    assert len(events) >= 3  # at least 2 text + 1 usage

    # Last event is the usage event
    usage_ev = events[-1]
    assert usage_ev.type == "usage"
    assert usage_ev.metadata["usage"]["prompt_tokens"] == 50
    assert usage_ev.metadata["usage"]["completion_tokens"] == 120
    assert usage_ev.metadata["usage"]["total_tokens"] == 170
    assert usage_ev.metadata["cost_usd"] == 0.0042
    assert usage_ev.metadata["duration_ms"] == 150.0
    assert usage_ev.metadata["tools_used"] == ["search"]


@pytest.mark.asyncio
async def test_stream_usage_event_with_no_usage_data(definition, opts):
    """stream() yields a usage event even when usage data is empty."""

    class NoUsageRuntime:
        async def prepare(self, definition, run_options):
            return {}

        async def run_stream(self, prepared, variables, events):
            await events.on_delta("ok")
            # Complete without usage data
            complete_event = StreamCompleteEvent(total_chunks=1, duration_ms=50.0)
            complete_event.metadata = {}
            await events.on_complete(complete_event)
            return
            yield

    runner = AgentRunner()
    with patch(
        "steer_llm_sdk.agents.runner.agent_runner.get_agent_runtime",
        return_value=NoUsageRuntime(),
    ):
        events = []
        async for ev in runner.stream(definition, {"query": "hi"}, opts):
            events.append(ev)

    usage_ev = events[-1]
    assert usage_ev.type == "usage"
    # usage should be empty dict (not None) — callers can safely check keys
    assert usage_ev.metadata["usage"] == {}
    assert usage_ev.metadata["cost_usd"] is None
    assert usage_ev.metadata["duration_ms"] == 50.0


@pytest.mark.asyncio
async def test_stream_text_events_precede_usage(definition, opts):
    """All text events come before the usage event."""
    runner = AgentRunner()

    fake_runtime = FakeRuntime()
    with patch(
        "steer_llm_sdk.agents.runner.agent_runner.get_agent_runtime",
        return_value=fake_runtime,
    ):
        events = []
        async for ev in runner.stream(definition, {"query": "hi"}, opts):
            events.append(ev)

    text_events = [e for e in events if e.type == "text"]
    usage_events = [e for e in events if e.type == "usage"]

    assert len(text_events) == 2
    assert len(usage_events) == 1
    assert text_events[0].content == "Hello "
    assert text_events[1].content == "world!"

    # Usage must be after all text
    last_text_idx = max(i for i, e in enumerate(events) if e.type == "text")
    usage_idx = next(i for i, e in enumerate(events) if e.type == "usage")
    assert usage_idx > last_text_idx
