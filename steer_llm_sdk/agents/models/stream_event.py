"""Structured streaming event model for AgentRunner.stream()."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StreamEvent:
    """A structured event yielded by AgentRunner.stream().

    Attributes:
        type: Event type — "text", "tool_call", "tool_result", "error", or "usage".
        content: Text content (populated when type="text").
        tool: Tool name (populated when type="tool_call").
        metadata: Arbitrary extra data from the runtime.
            When type="usage", metadata contains:
                - usage: dict with prompt_tokens, completion_tokens, total_tokens
                - cost_usd: estimated cost (float or None)
                - duration_ms: stream duration in milliseconds
                - tools_used: list of tool names called during the run
    """

    type: str  # "text" | "tool_call" | "tool_result" | "error" | "usage"
    content: str = ""
    tool: str = ""
    metadata: dict = field(default_factory=dict)
