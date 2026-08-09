# backend/knowledge/providers/duckduckgo_provider.py
from __future__ import annotations

import time
import urllib.parse
from typing import Any

from core.egress import EgressDenied, get_gate

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

        # DDGS opens its own connection, so the gate cannot carry these bytes
        # the way it carries Wikipedia's and GitHub's. It can still own the
        # *decision*, which is the property that matters: ask first, and under
        # default deny the library is never constructed and nothing leaves.
        #
        # Without this, the module was exempted in test_egress_chokepoint.py as
        # "dormant: web search is off until policy exists" while
        # test_knowledge_runtime.py called search() for real. That guard checks
        # reachability *at boot*, so it passed while the suite itself made the
        # unlogged live request the gate exists to record.
        #
        # The query string is the user's question, which is exactly the
        # outbound text Rule 3 exists to record.
        probe = "https://duckduckgo.com/?q=" + urllib.parse.quote(query)
        try:
            get_gate().check(probe, source="duckduckgo")
        except EgressDenied as e:
            # The user's policy refused. Distinct from a provider fault, so the
            # health view does not report a working provider as degraded.
            self._last_error = str(e)
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
