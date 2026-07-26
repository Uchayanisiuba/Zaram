# backend/knowledge/providers/markdown_provider.py
from __future__ import annotations

from typing import Any
from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider


class MarkdownProvider(BaseKnowledgeProvider):
    """Searches markdown documents."""

    def __init__(self):
        super().__init__("markdown", ResultType.DOCUMENT, cache_ttl=0)
        self._last_error: str | None = "Document search not configured"

    def search(self, query: str, max_results: int = 5) -> list[KnowledgeResult]:
        # Placeholder: will be connected to document search in future sprint
        return []

    def is_available(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "last_error": self._last_error,
        }
