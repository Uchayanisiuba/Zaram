"""SearXNG search provider (self-hosted)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..unified import SearchProvider, SearchResult
from backend.network.session import ZaramGovernedSession, ZaramSecurityViolation


class SearXNGProvider(SearchProvider):
    """SearXNG search provider for self-hosted instances."""

    name = "searxng"
    rate_limit_rpm = 60  # Higher since self-hosted

    def __init__(
        self,
        base_url: str,
        governed_session: ZaramGovernedSession,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session = governed_session

    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Execute a search via SearXNG API through the governed session."""
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
        }

        try:
            async with self._session.get(
                f"{self.base_url}/search",
                params=params,
                source="searxng",
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"SearXNG API error {resp.status}: {error_text}")

                data = await resp.json()

        except ZaramSecurityViolation as e:
            raise Exception(f"Egress blocked: {e}") from e

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                provider="searxng",
                score=item.get("score", 0.0) if "score" in item else 1.0,
                published=item.get("publishedDate"),
                metadata={"raw": item, "engine": item.get("engine")},
            ))

        return results

    async def health_check(self) -> Dict[str, Any]:
        """Check SearXNG health through the governed session."""
        try:
            params = {"q": "test", "format": "json", "pageno": 1}
            async with self._session.get(
                f"{self.base_url}/search",
                params=params,
                source="searxng",
            ) as resp:
                return {
                    "status": "healthy" if resp.status == 200 else "degraded",
                    "provider": "searxng",
                    "status_code": resp.status,
                    "url": self.base_url,
                }
        except ZaramSecurityViolation as e:
            return {"status": "egress_blocked", "provider": "searxng", "error": str(e), "url": self.base_url}
        except Exception as e:
            return {"status": "unhealthy", "provider": "searxng", "error": str(e), "url": self.base_url}

    async def close(self) -> None:
        """Close the governed session (delegates to underlying session)."""
        pass