from __future__ import annotations

import time
from typing import Any, Dict, Optional


class IdempotencyManager:
    def __init__(self, ttl_seconds: int = 900, max_entries: int = 1000) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: Dict[str, tuple[float, Any]] = {}

    def check_duplicate(self, key: str) -> Optional[Any]:
        now = time.time()
        item = self._store.get(key)
        if not item:
            return None
        ts, value = item
        if now - ts > self.ttl:
            # expired
            self._store.pop(key, None)
            return None
        return value

    def store_result(self, key: str, result: Any) -> None:
        # LRU-style eviction by size (approximate: pop oldest by timestamp)
        if len(self._store) >= self.max_entries:
            oldest_key = min(self._store.items(), key=lambda kv: kv[1][0])[0]
            self._store.pop(oldest_key, None)
        self._store[key] = (time.time(), result)

    def cleanup_expired(self) -> None:
        now = time.time()
        to_delete = [k for k, (ts, _) in self._store.items() if now - ts > self.ttl]
        for k in to_delete:
            self._store.pop(k, None)


