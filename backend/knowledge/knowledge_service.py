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


# Singleton runtime instance.
#
# **This one is wired to nothing, and that was the bug.** `KnowledgeRuntime()`
# with no arguments has `internet_runtime=None`, `memory_runtime=None` and an
# empty provider list — so `search()` queried no web and no memory, and
# `list_providers()` returned nothing. `POST /knowledge/search` therefore
# answered every query with zero results, and the provider-health block in
# `main.py` reported on an object with no providers to report.
#
# Meanwhile `bootstrapper._init_knowledge_runtime` builds a *different*
# instance, with the internet runtime, the memory runtime and twelve
# providers, and registers it for the capability router — which is why chat
# searched the web correctly while the HTTP endpoint did not. Two instances,
# different capabilities, and which one answered depended on how you arrived.
#
# The same shape the bootstrapper's own comment already records one layer
# down: registering something looked like wiring and was not.
_fallback_runtime = KnowledgeRuntime()

#: The wired instance, handed over by the bootstrapper at boot.
#:
#: Kept as an override rather than by constructing the real thing here,
#: because this module must stay importable with no event loop, no Spine and
#: no network — it is imported by tests and by tools that only want
#: `classify_query`. Unset, everything behaves exactly as it did.
_runtime: KnowledgeRuntime | None = None


def set_runtime(runtime: KnowledgeRuntime | None) -> None:
    """Hand this module the wired runtime, or ``None`` to fall back.

    Called once, by the bootstrapper, after the providers are registered.
    """
    global _runtime
    _runtime = runtime


def search_knowledge(query: str, persona: str = "zaram_prime", max_results: int = 6) -> dict:
    """Search knowledge across all providers.

    This is a backward-compatible wrapper around KnowledgeRuntime.search().
    The return format matches the historical knowledge_service API.
    """
    start = time.time()
    # Through `get_runtime()` rather than the module global, so this reaches
    # the wired instance when the app has booted. Reading the global directly
    # is what pinned this endpoint to the empty one.
    response = get_runtime().search(query, max_results=max_results)
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
    """The wired runtime if the app has booted, else the empty fallback.

    The fallback is kept rather than raising, because this module is imported
    in contexts that never boot — tests, and callers that only want
    `classify_query`. An empty result set is the honest answer there; what was
    wrong was serving it from a booted app that had a working runtime sitting
    beside it.
    """
    return _runtime if _runtime is not None else _fallback_runtime
