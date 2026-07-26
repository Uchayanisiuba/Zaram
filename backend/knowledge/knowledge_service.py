# backend/knowledge/knowledge_service.py
"""
Legacy knowledge service facade.

Maintains backward compatibility with existing code paths while
delegating to the new KnowledgeRuntime internally.
"""
from __future__ import annotations

import time
from typing import Any

from .runtime import KnowledgeRuntime
from .protocol import KnowledgeResult


# Singleton runtime instance
_runtime = KnowledgeRuntime()


def search_knowledge(query: str, persona: str = "zaram_prime", max_results: int = 6) -> dict:
    """Search knowledge across all providers.

    This is a backward-compatible wrapper around KnowledgeRuntime.search().
    The return format matches the historical knowledge_service API.
    """
    start = time.time()
    response = _runtime.search(query, max_results=max_results)
    latency_ms = (time.time() - start) * 1000

    return {
        "query": response.query,
        "persona": persona,
        "results": [r.to_dict() if hasattr(r, "to_dict") else _result_to_dict(r) for r in response.results],
        "total_results": len(response.results),
        "status": response.status.value,
        "provider": response.providers_consulted[0] if response.providers_consulted else "none",
        "providers_consulted": response.providers_consulted,
        "provider_status": response.provider_status,
        "search_duration_ms": response.latency_ms or latency_ms,
    }


def _result_to_dict(r: KnowledgeResult) -> dict[str, Any]:
    return {
        "title": r.title,
        "url": r.url,
        "snippet": r.snippet,
        "provider": r.provider,
        "published": r.published,
        "confidence": r.confidence,
        "score": r.score,
        "type": r.type.value if hasattr(r.type, "value") else str(r.type),
    }


# ---------------------------------------------------------------------------
# Legacy helpers (preserved for backward compatibility)
# ---------------------------------------------------------------------------

def classify_query(query: str) -> str:
    """Legacy query classifier. Preserved for backward compatibility."""
    q = query.lower()
    if any(w in q for w in ["weather", "temperature", "forecast"]):
        return "weather"
    if any(w in q for w in ["stock", "price", "finance", "market", "bitcoin", "crypto"]):
        return "finance"
    if any(w in q for w in ["release", "changelog", "update notes", "version"]):
        return "software_release"
    if any(w in q for w in ["news", "headlines", "breaking"]):
        return "news"
    if any(w in q for w in ["who is", "who was", "biography"]):
        return "people"
    return "general"


def get_runtime() -> KnowledgeRuntime:
    """Get the singleton KnowledgeRuntime instance."""
    return _runtime
