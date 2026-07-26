# backend/knowledge/providers/wikipedia_provider.py
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Any
from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider, SearchMixin


class WikipediaProvider(BaseKnowledgeProvider):
    """Searches Wikipedia for encyclopedic knowledge."""

    def __init__(self):
        super().__init__("wikipedia", ResultType.WEB, cache_ttl=3600)
        self._last_error: str | None = None

    def search(self, query: str, max_results: int = 5) -> list[KnowledgeResult]:
        url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={urllib.parse.quote(query)}"
            f"&format=json&srlimit={max_results}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Zaram/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = __import__("json").loads(r.read())
            self._last_error = None
        except Exception as e:
            self._last_error = str(e)
            return []

        results = []
        for r in (data.get("query", {}).get("search") or [])[:max_results]:
            title = r.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", r.get("snippet") or "")
            results.append(SearchMixin.make_result(
                title=title,
                url=f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                snippet=snippet,
                provider="wikipedia",
                confidence=0.7,
                result_type=ResultType.WEB,
            ))
        return results

    def is_available(self) -> bool:
        return True

    def health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._last_error is None else "degraded",
            "last_error": self._last_error,
        }
