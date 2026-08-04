# backend/knowledge/providers/wikipedia_provider.py
from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from core.egress import EgressDenied, get_gate

from ..protocol import KnowledgeResult, ResultType
from .base import BaseKnowledgeProvider, SearchMixin


class WikipediaProvider(BaseKnowledgeProvider):
    """Searches Wikipedia for encyclopedic knowledge."""

    def __init__(self):
        super().__init__("wikipedia", ResultType.WEB, cache_ttl=3600)
        self._last_error: str | None = None

    def search(self, query: str, max_results: int = 5) -> list[KnowledgeResult]:
        url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={urllib.parse.quote(query)}"
            f"&format=json&srlimit={max_results}"
        )
        # Through the gate, never directly. The query string is the user's
        # question, so this is exactly the outbound text Rule 3 exists to record.
        try:
            data = json.loads(get_gate().request(url, timeout=10, source="wikipedia"))
            self._last_error = None
        except EgressDenied as e:
            # Not a provider failure — the user's policy said no. Kept distinct
            # so the health view does not report a working provider as degraded.
            self._last_error = str(e)
            return []
        except Exception as e:
            self._last_error = str(e)
            return []

        results = []
        for r in (data.get("query", {}).get("search") or [])[:max_results]:
            title = r.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", r.get("snippet") or "")
            results.append(SearchMixin.make_result(
                title=title,
                url=f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                snippet=snippet,
                provider="wikipedia",
                confidence=0.7,
                result_type=ResultType.WEB,
            ))
        return results

    def is_available(self) -> bool:
        return True

    def health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._last_error is None else "degraded",
            "last_error": self._last_error,
        }
