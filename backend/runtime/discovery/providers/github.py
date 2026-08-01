# backend/runtime/discovery/providers/github.py
from __future__ import annotations

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


class GitHubProvider(BaseDiscoveryProvider):
    """Searches GitHub repositories and releases."""

    def __init__(self) -> None:
        super().__init__(
            "github",
            "programming",
            cache_ttl=300,
            capabilities=[Capability.CODE, Capability.REPOSITORIES, Capability.DOCUMENTATION],
            authority=AuthorityLevel.GITHUB,
            cost=0.0,
            avg_latency_ms=300.0,
        )

    async def discover(
        self, request: Any, context: Any
    ) -> list[DiscoveryResult]:
        max_results = request.max_results
        url = (
            "https://api.github.com/search/repositories"
            f"?q={urllib.parse.quote(request.query)}"
            f"&sort=updated&per_page={max_results}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Zaram/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                import json
                data = json.loads(r.read())
            self._last_error = None
            self._record_success()
        except Exception as exc:
            self._record_failure(str(exc))
            return []

        results: list[DiscoveryResult] = []
        for item in (data.get("items") or [])[:max_results]:
            metadata = DiscoveryMetadata(
                provider="github",
                url=item.get("html_url", ""),
                title=item.get("full_name", ""),
                author=item.get("owner", {}).get("login"),
                language=item.get("language", "en"),
                confidence=0.75,
                freshness=FreshnessLevel.RECENT,
                raw_metadata={
                    "stars": item.get("stargazers_count"),
                    "description": item.get("description"),
                },
            )
            snippet = item.get("description") or ""
            results.append(DiscoveryResult(
                content=snippet,
                summary=snippet,
                metadata=metadata,
                confidence=0.75,
                freshness=FreshnessLevel.RECENT,
                provider="github",
                retrieval_time=0.0,
            ))
        return results
