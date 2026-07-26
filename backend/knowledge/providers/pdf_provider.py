# backend/knowledge/providers/pdf_provider.py
from __future__ import annotations

from typing import Any
from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider


class PDFProvider(BaseKnowledgeProvider):
    """Searches PDF documents."""

    def __init__(self):
        super().__init__("pdf", ResultType.DOCUMENT, cache_ttl=0)
        self._last_error: str | None = "PDF parsing not configured"

    def search(self, query: str, max_results: int = 5) -> list[KnowledgeResult]:
        # Placeholder: will be connected to PDF parsing in future sprint
        return []

    def is_available(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "last_error": self._last_error,
        }
