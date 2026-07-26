# backend/knowledge/providers/rss_provider.py
from __future__ import annotations

from typing import Any
from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider


class RSSProvider(BaseKnowledgeProvider):
    """Searches RSS feeds for recent articles."""

    def __init__(self):
        super().__init__("rss", ResultType.RSS, cache_ttl=600)
        self._last_error: str | None = "RSS feeds not configured"

    def search(self, query: str, max_results: int = 5) -> list[KnowledgeResult]:
        # Placeholder: will be connected to RSS feeds in future sprint
        return []

    def is_available(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "last_error": self._last_error,
        }
