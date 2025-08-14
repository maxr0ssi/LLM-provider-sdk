from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Union


DeltaType = Literal["text", "json"]


@dataclass
class StreamDelta:
    kind: DeltaType
    value: Union[str, Dict[str, Any]]


