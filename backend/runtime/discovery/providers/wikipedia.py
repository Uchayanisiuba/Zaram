# backend/runtime/discovery/providers/wikipedia.py
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Any

from ..contracts import (
    AuthorityLevel,
    Capability,
    DiscoveryMetadata,
    DiscoveryResult,
    FreshnessLevel,
)
from .base import BaseDiscoveryProvider


class WikipediaProvider(BaseDiscoveryProvider):
    """Searches Wikipedia for encyclopedic knowledge."""

    def __init__(self) -> None:
        super().__init__(
            "wikipedia",
            "encyclopedia",
            cache_ttl=3600,
            capabilities=[Capability.REFERENCE, Capability.ACADEMIC, Capability.DOCUMENTATION],
            authority=AuthorityLevel.WIKIPEDIA,
            cost=0.0,
            avg_latency_ms=200.0,
        )

    async def discover(
        self, request: Any, context: Any
    ) -> list[DiscoveryResult]:
        query = request.query
        max_results = request.max_results
        url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={urllib.parse.quote(query)}"
            f"&format=json&srlimit={max_results}"
        )
        # Through the gate. The discovery runtime is deliberately unreachable
        # from the chat path until the egress log and per-source policy exist —
        # this is what it will be reachable *through* when that changes.
        try:
            import json

            from core.egress import get_gate

            data = json.loads(get_gate().request(url, timeout=10, source="discovery.wikipedia"))
            self._last_error = None
            self._record_success()
        except Exception as exc:
            self._record_failure(str(exc))
            return []

        results: list[DiscoveryResult] = []
        for item in (data.get("query", {}).get("search") or [])[:max_results]:
            title = item.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", item.get("snippet") or "")
            metadata = DiscoveryMetadata(
                provider="wikipedia",
                url=f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                title=title,
                language="en",
                confidence=0.7,
                freshness=FreshnessLevel.STATIC,
            )
            results.append(DiscoveryResult(
                content=snippet,
                summary=snippet,
                metadata=metadata,
                confidence=0.7,
                freshness=FreshnessLevel.STATIC,
                provider="wikipedia",
                retrieval_time=0.0,
            ))
        return results
