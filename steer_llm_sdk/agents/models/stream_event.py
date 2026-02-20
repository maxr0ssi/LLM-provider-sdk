"""Structured streaming event model for AgentRunner.stream()."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StreamEvent:
    """A structured event yielded by AgentRunner.stream().

    Attributes:
        type: Event type — "text", "tool_call", "tool_result", or "error".
        content: Text content (populated when type="text").
        tool: Tool name (populated when type="tool_call").
        metadata: Arbitrary extra data from the runtime.
    """

    type: str  # "text" | "tool_call" | "tool_result" | "error"
    content: str = ""
    tool: str = ""
    metadata: dict = field(default_factory=dict)
