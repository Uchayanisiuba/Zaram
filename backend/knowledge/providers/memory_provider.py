# backend/knowledge/providers/memory_provider.py
from __future__ import annotations

from typing import Any
from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider, SearchMixin


class MemoryProvider(BaseKnowledgeProvider):
    """Searches local conversation memory and embeddings via the Memory Runtime."""

    def __init__(self, memory_runtime=None):
        super().__init__("memory", ResultType.MEMORY, cache_ttl=0)
        self._memory_runtime = memory_runtime
        self._last_error: str | None = None

    def search(self, query: str, max_results: int = 5) -> list[KnowledgeResult]:
        if not self._memory_runtime:
            self._last_error = "Memory Runtime not connected"
            return []

        # run_sync, not a fresh event loop: this is called from inside FastAPI's
        # running loop, where creating and running another loop raises.
        from core.async_bridge import run_sync

        try:
            results = run_sync(self._memory_runtime.retrieve(
                query=query,
                max_results=max_results,
            ))
        except Exception as e:
            self._last_error = str(e)
            return []

        self._last_error = None
        self._record_success()

        knowledge_results = []
        for r in results:
            knowledge_results.append(KnowledgeResult(
                title=r.record.content[:80],
                url=f"memory:{r.record.id}",
                snippet=r.record.content[:300],
                provider="memory",
                confidence=r.score,
                type=ResultType.MEMORY,
                metadata={
                    "memory_type": r.record.memory_type.value,
                    "match_reason": r.match_reason,
                    "record_id": r.record.id,
                },
                retrieved_at=r.record.created_at,
            ))
        return knowledge_results

    def is_available(self) -> bool:
        return self._memory_runtime is not None

    def health(self) -> dict[str, Any]:
        if self._memory_runtime:
            runtime_health = self._memory_runtime.health_check()
            return {
                "status": "healthy" if runtime_health.get("state") == "ready" else "degraded",
                "last_error": self._last_error,
                "runtime_state": runtime_health.get("state", "unknown"),
            }
        return {
            "status": "unavailable",
            "last_error": self._last_error or "Memory Runtime not connected",
        }
