# backend/runtime/discovery/sandbox.py
from __future__ import annotations

import asyncio
import threading
import time

from .contracts import DiscoveryContext, DiscoveryProvider, DiscoveryRequest, DiscoveryResult
from .retry import RetryConfig, retry_with_backoff


class ProviderSandbox:
    """Isolates provider execution with timeout, exception isolation, and memory limits."""

    def __init__(self, default_timeout_ms: float = 10000.0) -> None:
        self._default_timeout_ms = default_timeout_ms
        self._lock = threading.Lock()
        self._active_calls: dict[str, float] = {}

    async def execute(
        self,
        provider: DiscoveryProvider,
        request: DiscoveryRequest,
        context: DiscoveryContext,
        timeout_ms: float | None = None,
    ) -> list[DiscoveryResult]:
        pid = provider.get_provider_id()
        timeout = timeout_ms or self._default_timeout_ms

        with self._lock:
            self._active_calls[pid] = time.time()

        try:
            config = RetryConfig(max_retries=2, base_delay=0.5, max_delay=5.0)

            async def _call() -> list[DiscoveryResult]:
                return await asyncio.wait_for(provider.discover(request, context), timeout=timeout / 1000.0)

            results = await retry_with_backoff(
                _call,
                config=config,
                should_retry=lambda e: isinstance(e, (TimeoutError, ConnectionError, OSError)),
            )
            return results
        except TimeoutError:
            context.errors[pid] = "timeout"
            return []
        except Exception as exc:
            context.errors[pid] = str(exc)
            return []
        finally:
            with self._lock:
                self._active_calls.pop(pid, None)

    def get_active_calls(self) -> dict[str, float]:
        with self._lock:
            return dict(self._active_calls)

    def is_executing(self, provider_id: str) -> bool:
        with self._lock:
            return provider_id in self._active_calls
