# backend/runtime/discovery/retry.py
from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class RetryConfig:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


async def retry_with_backoff(
    func: Callable[[], Any],
    config: RetryConfig | None = None,
    should_retry: Callable[[Exception], bool] | None = None,
) -> Any:
    if config is None:
        config = RetryConfig()

    last_exception: Exception | None = None
    for attempt in range(config.max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            return func()
        except Exception as exc:
            last_exception = exc
            if should_retry is not None and not should_retry(exc):
                raise
            if attempt >= config.max_retries:
                raise
            delay = min(
                config.base_delay * (config.exponential_base ** attempt),
                config.max_delay,
            )
            if config.jitter:
                delay = delay * (0.5 + random.random())
            await asyncio.sleep(delay)

    raise last_exception  # type: ignore[misc]
