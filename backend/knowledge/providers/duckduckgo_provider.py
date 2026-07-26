# backend/knowledge/providers/duckduckgo_provider.py
from __future__ import annotations

import time
from typing import Any
from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider, SearchMixin

try:
    from duckduckgo_search import DDGS  # type: ignore
except Exception:  # pragma: no cover
    DDGS = None  # type: ignore


class DuckDuckGoProvider(BaseKnowledgeProvider):
    """Searches DuckDuckGo for web results."""

    def __init__(self):
        super().__init__("duckduckgo", ResultType.WEB, cache_ttl=900)
        self._last_error: str | None = None
        self._available = DDGS is not None

    def search(self, query: str, max_results: int = 6) -> list[KnowledgeResult]:
        if DDGS is None:
            self._last_error = "duckduckgo-search package not installed"
            return []
        
        results = []
        for attempt in range(3):
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=max_results):
                        url = r.get("href") or r.get("url")
                        if not url:
                            continue
                        results.append(SearchMixin.make_result(
                            title=r.get("title", ""),
                            url=url,
                            snippet=(r.get("body") or "")[:280],
                            provider="duckduckgo",
                            confidence=0.6,
                            result_type=ResultType.WEB,
                        ))
                self._last_error = None
                break
            except Exception as e:
                self._last_error = str(e)
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    return []
        return results[:max_results]

    def is_available(self) -> bool:
        return self._available

    def health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._available and self._last_error is None else "degraded" if self._available else "unavailable",
            "last_error": self._last_error,
            "available": self._available,
        }
