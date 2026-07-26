# backend/knowledge/providers/placeholder_provider.py
from __future__ import annotations

from typing import Any
from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider


class PlaceholderProvider(BaseKnowledgeProvider):
    """Placeholder for future providers (Gmail, Notion, Drive, etc.)."""

    def __init__(self, provider_id: str = "placeholder"):
        super().__init__(provider_id, ResultType.PLACEHOLDER, cache_ttl=0)
        self._last_error: str | None = "Provider not implemented"

    def search(self, query: str, max_results: int = 5) -> list[KnowledgeResult]:
        return []

    def is_available(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "last_error": self._last_error,
        }
