from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Union


DeltaType = Literal["text", "json"]


@dataclass
class StreamDelta:
    """Normalized streaming delta from LLM providers.
    
    Attributes:
        kind: Type of delta (text or json)
        value: The actual content (text string or json dict)
        provider: Name of the provider that generated this delta
        raw_event: Original provider event for debugging
        metadata: Additional metadata about this delta
    """
    kind: DeltaType
    value: Union[str, Dict[str, Any]]
    provider: str
    raw_event: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def get_text(self) -> str:
        """Extract text content from delta.
        
        Returns:
            Text content as string
        """
        if self.kind == "text":
            return str(self.value)
        elif self.kind == "json" and isinstance(self.value, dict):
            return self.value.get("text", "")
        return ""


