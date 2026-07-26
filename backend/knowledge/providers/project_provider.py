# backend/knowledge/providers/project_provider.py
from __future__ import annotations

from typing import Any
from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider


class ProjectProvider(BaseKnowledgeProvider):
    """Searches local project files and workspace context."""

    def __init__(self):
        super().__init__("project", ResultType.PROJECT, cache_ttl=0)
        self._last_error: str | None = "Workspace runtime not connected"

    def search(self, query: str, max_results: int = 5) -> list[KnowledgeResult]:
        # Placeholder: will be connected to Workspace Runtime in future sprint
        return []

    def is_available(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "last_error": self._last_error,
        }
