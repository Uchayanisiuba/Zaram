# backend/runtime/discovery/registry.py
from __future__ import annotations

import threading
from typing import Any

from .contracts import DiscoveryProvider, ProviderStatus


class ProviderRegistry:
    """Dynamic registry for discovery providers."""

    def __init__(self) -> None:
        self._providers: dict[str, DiscoveryProvider] = {}
        self._lock = threading.Lock()

    def register(self, provider: DiscoveryProvider) -> None:
        with self._lock:
            pid = provider.get_provider_id()
            if pid in self._providers:
                raise ValueError(f"Provider {pid} is already registered")
            self._providers[pid] = provider

    def remove(self, provider_id: str) -> None:
        with self._lock:
            self._providers.pop(provider_id, None)

    def get(self, provider_id: str) -> DiscoveryProvider | None:
        with self._lock:
            return self._providers.get(provider_id)

    def list(self) -> list[DiscoveryProvider]:
        with self._lock:
            return list(self._providers.values())

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._providers.keys())

    def health_check(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        with self._lock:
            for pid, provider in self._providers.items():
                try:
                    result[pid] = provider.health_check()
                except Exception as exc:
                    result[pid] = {"status": ProviderStatus.ERROR.value, "error": str(exc)}
        return result

    def get_by_priority(self) -> list[DiscoveryProvider]:
        with self._lock:
            return sorted(self._providers.values(), key=lambda p: -p.priority())

    def get_available(self) -> list[DiscoveryProvider]:
        with self._lock:
            return [p for p in self._providers.values() if p.is_available()]

    def get_by_type(self, provider_type: str) -> list[DiscoveryProvider]:
        with self._lock:
            return [
                p for p in self._providers.values() if p.get_provider_type() == provider_type
            ]
