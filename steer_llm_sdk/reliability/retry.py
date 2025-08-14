from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Iterable, Type


@dataclass
class RetryConfig:
    max_attempts: int = 2
    backoff_factor: float = 2.0
    retryable_errors: Iterable[Type[Exception]] = ()


class RetryManager:
    async def execute_with_retry(self, func: Callable, config: RetryConfig):
        attempt = 0
        delay = 0.25
        while True:
            try:
                return await func()
            except Exception as e:  # noqa: BLE001
                attempt += 1
                if attempt >= config.max_attempts or not any(isinstance(e, t) for t in config.retryable_errors):
                    raise
                await asyncio.sleep(delay)
                delay *= config.backoff_factor


