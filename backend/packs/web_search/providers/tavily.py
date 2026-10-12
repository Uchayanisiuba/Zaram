"""Tavily search provider."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..unified import SearchProvider, SearchResult
from backend.network.session import ZaramGovernedSession, ZaramSecurityViolation


class TavilyProvider(SearchProvider):
    """Tavily search API provider."""

    name = "tavily"
    rate_limit_rpm = 20  # Conservative default

    def __init__(
        self,
        api_key: str,
        governed_session: ZaramGovernedSession,
    ):
        self.api_key = api_key
        self.base_url = "https://api.tavily.com"
        self._session = governed_session

    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Execute a search via Tavily API through the governed session."""
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
        }

        try:
            async with self._session.post(
                f"{self.base_url}/search",
                json=payload,
                source="tavily",
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Tavily API error {resp.status}: {error_text}")

                data = await resp.json()

        except ZaramSecurityViolation as e:
            raise Exception(f"Egress blocked: {e}") from e

        results = []
        for item in data.get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                provider="tavily",
                score=item.get("score", 0.0),
                published=item.get("published_date"),
                metadata={"raw": item},
            ))

        return results

    async def health_check(self) -> Dict[str, Any]:
        """Check Tavily API health through the governed session."""
        try:
            payload = {"api_key": self.api_key, "query": "test", "max_results": 1}
            async with self._session.post(
                f"{self.base_url}/search",
                json=payload,
                source="tavily",
            ) as resp:
                return {
                    "status": "healthy" if resp.status == 200 else "degraded",
                    "provider": "tavily",
                    "status_code": resp.status,
                }
        except ZaramSecurityViolation as e:
            return {"status": "egress_blocked", "provider": "tavily", "error": str(e)}
        except Exception as e:
            return {"status": "unhealthy", "provider": "tavily", "error": str(e)}

    async def close(self) -> None:
        """Close the governed session (delegates to underlying session)."""
        # The governed session is managed by the caller, not the provider
        pass