"""Brave search provider."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..unified import SearchProvider, SearchResult
from backend.network.session import ZaramGovernedSession, ZaramSecurityViolation


class BraveProvider(SearchProvider):
    """Brave Search API provider."""

    name = "brave"
    rate_limit_rpm = 20  # Conservative default

    def __init__(
        self,
        api_key: str,
        governed_session: ZaramGovernedSession,
    ):
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com"
        self._session = governed_session

    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Execute a search via Brave API through the governed session."""
        params = {
            "q": query,
            "count": min(max_results, 20),
            "search_lang": "en",
        }

        try:
            async with self._session.get(
                f"{self.base_url}/res/v1/web/search",
                params=params,
                source="brave",
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Brave API error {resp.status}: {error_text}")

                data = await resp.json()

        except ZaramSecurityViolation as e:
            raise Exception(f"Egress blocked: {e}") from e

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                provider="brave",
                score=1.0,  # Brave doesn't provide scores
                published=item.get("age"),
                metadata={"raw": item},
            ))

        return results

    async def health_check(self) -> Dict[str, Any]:
        """Check Brave API health through the governed session."""
        try:
            params = {"q": "test", "count": 1}
            async with self._session.get(
                f"{self.base_url}/res/v1/web/search",
                params=params,
                source="brave",
            ) as resp:
                return {
                    "status": "healthy" if resp.status == 200 else "degraded",
                    "provider": "brave",
                    "status_code": resp.status,
                }
        except ZaramSecurityViolation as e:
            return {"status": "egress_blocked", "provider": "brave", "error": str(e)}
        except Exception as e:
            return {"status": "unhealthy", "provider": "brave", "error": str(e)}

    async def close(self) -> None:
        """Close the governed session (delegates to underlying session)."""
        # The governed session is managed by the caller, not the provider
        pass