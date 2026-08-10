# backend/runtime/discovery/providers/base.py
from __future__ import annotations

import time
from typing import Any

from ..contracts import (
    AuthorityLevel,
    Capability,
    ProviderStatus,
)


class BaseDiscoveryProvider:
    """Base class providing common functionality for all discovery providers."""

    def __init__(
        self,
        provider_id: str,
        provider_type: str,
        cache_ttl: int = 900,
        capabilities: list[Capability] | None = None,
        authority: AuthorityLevel = AuthorityLevel.UNKNOWN,
        cost: float = 0.0,
        avg_latency_ms: float = 0.0,
    ) -> None:
        self._id = provider_id
        self._type = provider_type
        self._cache_ttl = cache_ttl
        self._capabilities = capabilities or []
        self._authority = authority
        self._cost = cost
        self._avg_latency_ms = avg_latency_ms
        self._last_search_time = 0.0
        self._request_count = 0
        self._failure_count = 0
        self._success_count = 0
        self._last_error: str | None = None

    def get_provider_id(self) -> str:
        return self._id

    def get_provider_type(self) -> str:
        return self._type

    def get_capabilities(self) -> list[Capability]:
        return list(self._capabilities)

    def get_authority_level(self) -> AuthorityLevel:
        return self._authority

    def estimated_cost(self) -> float:
        return self._cost

    def estimated_latency_ms(self) -> float:
        return self._avg_latency_ms

    def estimated_confidence(self) -> float:
        if self._request_count == 0:
            return 0.8
        return max(0.0, min(1.0, self._success_count / max(self._request_count, 1)))

    def is_available(self) -> bool:
        return True

    def priority(self) -> int:
        return 50

    def cache_ttl(self) -> int:
        return self._cache_ttl

    def _record_success(self, latency_ms: float = 0.0) -> None:
        self._request_count += 1
        self._success_count += 1
        self._last_search_time = time.time()
        if self._avg_latency_ms == 0:
            self._avg_latency_ms = latency_ms
        else:
            self._avg_latency_ms = (self._avg_latency_ms + latency_ms) / 2

    def _record_failure(self, error: str, latency_ms: float = 0.0) -> None:
        self._request_count += 1
        self._failure_count += 1
        self._last_error = error
        if self._avg_latency_ms == 0:
            self._avg_latency_ms = latency_ms
        else:
            self._avg_latency_ms = (self._avg_latency_ms + latency_ms) / 2

    def health_check(self) -> dict[str, Any]:
        available = self.is_available()
        status = ProviderStatus.HEALTHY if available and self._last_error is None else (
            ProviderStatus.DEGRADED if available else ProviderStatus.UNAVAILABLE
        )
        return {
            "status": status.value,
            "provider": self._id,
            "type": self._type,
            "priority": self.priority(),
            "cache_ttl": self._cache_ttl,
            "capabilities": [c.value for c in self._capabilities],
            "authority": self._authority.value,
            "last_sync": self._last_search_time,
            "requests": self._request_count,
            "successes": self._success_count,
            "failures": self._failure_count,
            "last_error": self._last_error,
        }
