from __future__ import annotations

import asyncio
import time
from typing import Any
from dataclasses import dataclass, field

from .contracts import (
    InternetConnector,
    SearchQuery,
    SearchResult,
    ConnectorHealth,
    InternetConnectorType,
    InternetStatus,
)


@dataclass
class BaseInternetConnector(InternetConnector):
    _connector_id: str
    _connector_type: InternetConnectorType
    _available: bool = True
    _last_error: str | None = None
    _stats: dict[str, Any] = field(default_factory=dict)

    def __init__(self, connector_id: str, connector_type: InternetConnectorType):
        self._connector_id = connector_id
        self._connector_type = connector_type
        self._available = True
        self._last_error = None
        self._stats = {
            "requests": 0,
            "successes": 0,
            "errors": 0,
            "total_latency_ms": 0.0,
            "last_request": 0.0,
        }

    def get_connector_id(self) -> str:
        return self._connector_id

    def get_connector_type(self) -> InternetConnectorType:
        return self._connector_type

    def is_available(self) -> bool:
        return self._available

    async def health_check(self) -> ConnectorHealth:
        stats = self._stats
        return ConnectorHealth(
            connector_id=self._connector_id,
            connector_type=self._connector_type,
            status=InternetStatus.HEALTHY if self._available else InternetStatus.UNAVAILABLE,
            latency_ms=stats["total_latency_ms"] / max(stats["requests"], 1),
            last_request=stats["last_request"],
            success_count=stats["successes"],
            error_count=stats["errors"],
            last_error=self._last_error,
        )

    def _record_success(self, latency_ms: float) -> None:
        self._stats["requests"] += 1
        self._stats["successes"] += 1
        self._stats["total_latency_ms"] += latency_ms
        self._stats["last_request"] = time.time()
        self._available = True
        self._last_error = None

    def _record_error(self, error: str, latency_ms: float = 0) -> None:
        self._stats["requests"] += 1
        self._stats["errors"] += 1
        self._stats["total_latency_ms"] += latency_ms
        self._stats["last_request"] = time.time()
        self._last_error = error
        if self._stats["errors"] > 5:
            self._available = False


class DuckDuckGoConnector(BaseInternetConnector):
    """DuckDuckGo HTML scrape connector."""

    def __init__(self):
        super().__init__("duckduckgo", InternetConnectorType.DUCKDUCKGO)
        self._ddgs = None
        self._init_ddgs()

    def _init_ddgs(self):
        try:
            from duckduckgo_search import DDGS
            self._ddgs = DDGS()
        except ImportError:
            self._available = False
            self._last_error = "duckduckgo-search not installed"

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        if not self._ddgs:
            self._init_ddgs()
            if not self._ddgs:
                return []

        start = time.time()
        results = []

        try:
            loop = asyncio.get_event_loop()
            ddgs_results = await loop.run_in_executor(
                None,
                lambda: list(self._ddgs.text(query.query, max_results=query.max_results))
            )

            for r in ddgs_results:
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", r.get("url", "")),
                    snippet=r.get("body", "")[:300],
                    connector=self._connector_id,
                    connector_type=self._connector_type,
                    score=0.6,
                    metadata={"source": "ddg_html"},
                ))

            self._record_success((time.time() - start) * 1000)
        except Exception as e:
            self._record_error(str(e), (time.time() - start) * 1000)

        return results


class WikipediaConnector(BaseInternetConnector):
    """Wikipedia API connector."""

    def __init__(self):
        super().__init__("wikipedia", InternetConnectorType.WIKIPEDIA)
        self._session = None

    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        start = time.time()
        results = []

        try:
            session = await self._get_session()
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query.query,
                "srlimit": query.max_results,
                "format": "json",
            }

            async with session.get(url, params=params) as resp:
                data = await resp.json()
                for item in data.get("query", {}).get("search", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=f"https://en.wikipedia.org/wiki/{item.get('title', '').replace(' ', '_')}",
                        snippet=item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")[:300],
                        connector=self._connector_id,
                        connector_type=self._connector_type,
                        score=0.8,
                        metadata={"pageid": item.get("pageid")},
                    ))

            self._record_success((time.time() - start) * 1000)
        except Exception as e:
            self._record_error(str(e), (time.time() - start) * 1000)

        return results


class GitHubConnector(BaseInternetConnector):
    """GitHub search connector."""

    def __init__(self, token: str | None = None):
        super().__init__("github", InternetConnectorType.GITHUB)
        self._token = token

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        start = time.time()
        results = []

        try:
            import aiohttp
            headers = {"Accept": "application/vnd.github.v3+json"}
            if self._token:
                headers["Authorization"] = f"token {self._token}"

            async with aiohttp.ClientSession(headers=headers) as session:
                url = "https://api.github.com/search/repositories"
                params = {"q": query.query, "per_page": query.max_results}

                async with session.get(url, params=params) as resp:
                    if resp.status == 403:
                        raise Exception("Rate limited")
                    data = await resp.json()
                    for item in data.get("items", []):
                        results.append(SearchResult(
                            title=item.get("full_name", ""),
                            url=item.get("html_url", ""),
                            snippet=item.get("description", "")[:300] if item.get("description") else "",
                            connector=self._connector_id,
                            connector_type=self._connector_type,
                            score=0.7,
                            metadata={"stars": item.get("stargazers_count"), "language": item.get("language")},
                        ))

            self._record_success((time.time() - start) * 1000)
        except Exception as e:
            self._record_error(str(e), (time.time() - start) * 1000)

        return results


class RSSConnector(BaseInternetConnector):
    """RSS feed connector."""

    def __init__(self, feed_url: str):
        super().__init__(f"rss_{feed_url}", InternetConnectorType.RSS)
        self._feed_url = feed_url

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        start = time.time()
        results = []

        try:
            import aiohttp
            import feedparser

            async with aiohttp.ClientSession() as session:
                async with session.get(self._feed_url) as resp:
                    content = await resp.text()

            feed = feedparser.parse(content)
            for entry in feed.entries[: query.max_results]:
                if query.query.lower() in (entry.get("title", "") + entry.get("summary", "")).lower():
                    results.append(SearchResult(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        snippet=entry.get("summary", "")[:300],
                        connector=self._connector_id,
                        connector_type=self._connector_type,
                        score=0.7,
                        metadata={"published": entry.get("published", "")},
                    ))

            self._record_success((time.time() - start) * 1000)
        except Exception as e:
            self._record_error(str(e), (time.time() - start) * 1000)

        return results


def create_connector(connector_type: InternetConnectorType, **kwargs) -> InternetConnector:
    if connector_type == InternetConnectorType.DUCKDUCKGO:
        return DuckDuckGoConnector()
    elif connector_type == InternetConnectorType.WIKIPEDIA:
        return WikipediaConnector()
    elif connector_type == InternetConnectorType.GITHUB:
        return GitHubConnector(kwargs.get("token"))
    elif connector_type == InternetConnectorType.RSS:
        return RSSConnector(kwargs.get("feed_url", ""))
    raise ValueError(f"Unknown connector type: {connector_type}")