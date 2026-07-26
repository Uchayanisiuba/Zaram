# backend/knowledge/providers/github_provider.py
from __future__ import annotations

import time
import urllib.parse
import urllib.request
from typing import Any
from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider, SearchMixin


class GitHubProvider(BaseKnowledgeProvider):
    """Searches GitHub repositories and releases."""

    def __init__(self):
        super().__init__("github", ResultType.GITHUB, cache_ttl=300)
        self._last_error: str | None = None

    def search(self, query: str, max_results: int = 5) -> list[KnowledgeResult]:
        results = []
        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=updated&per_page={max_results}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Zaram/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = __import__("json").loads(r.read())
            self._last_error = None
        except Exception as e:
            self._last_error = str(e)
            return []

        for item in (data.get("items") or [])[:max_results]:
            results.append(SearchMixin.make_result(
                title=item.get("full_name", ""),
                url=item.get("html_url", ""),
                snippet=item.get("description") or "",
                provider="github",
                confidence=0.75,
                result_type=ResultType.GITHUB,
            ))
        return results

    def is_available(self) -> bool:
        return True

    def health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._last_error is None else "degraded",
            "last_error": self._last_error,
        }
