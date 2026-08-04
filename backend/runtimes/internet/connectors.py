from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

try:
    from duckduckgo_search import DDGS
except Exception:
    DDGS = None

try:
    import wikipedia
except Exception:
    wikipedia = None

try:
    import feedparser
except Exception:
    feedparser = None

try:
    import aiohttp
except Exception:
    aiohttp = None


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    connector: str
    score: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchQuery:
    query: str
    max_results: int = 10
    connectors: list[str] | None = None


class InternetConnector(ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[SearchResult]: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]: ...


class InternetRuntime(ABC):
    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def shutdown(self) -> None: ...

    @abstractmethod
    def get_runtime_id(self) -> str: ...

    @abstractmethod
    def get_metadata(self) -> RuntimeMetadata: ...

    @abstractmethod
    def get_state(self) -> InternetStatus: ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]: ...

    @abstractmethod
    async def search(self, query: str, connectors: list[str] | None = None, max_results: int = 10) -> list[SearchResult]: ...


class InternetCache(ABC):
    @abstractmethod
    async def get(self, key: str) -> list[SearchResult] | None: ...

    @abstractmethod
    async def set(self, key: str, value: list[SearchResult], ttl: int | None = None) -> None: ...

    @abstractmethod
    async def clear(self) -> None: ...

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}


class InternetRanker(ABC):
    @abstractmethod
    async def rank(self, results: list[SearchResult], query: SearchQuery) -> list[SearchResult]: ...

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}


class InternetStatus(str):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"
    DISABLED = "disabled"


@dataclass
class RuntimeMetadata:
    runtime_id: str
    version: str
    priority: str = "normal"
    capabilities: list[Capability] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class Capability:
    id: str
    runtime_id: str
    version: str = "1.0.0"
    category: str = "general"
    locality: CapabilityLocality = CapabilityLocality.HYBRID


class CapabilityLocality(str):
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"
    REMOTE_DEVICE = "remote_device"


class DuckDuckGoConnector(InternetConnector):
    def __init__(self):
        self._id = "duckduckgo"
        self._available = DDGS is not None
        self._last_error: str | None = None

    @property
    def id(self) -> str:
        return self._id

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        if not self._available:
            return []

        results = []
        try:
            def _search():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))

            search_results = await asyncio.to_thread(_search)
            for r in search_results:
                url = r.get("href") or r.get("url")
                if url:
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=url,
                        snippet=(r.get("body") or "")[:300],
                        connector=self._id,
                        score=0.6,
                    ))
            self._last_error = None
        except Exception as e:
            self._last_error = str(e)
        return results

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._available and not self._last_error else "degraded" if self._available else "unavailable",
            "available": self._available,
            "last_error": self._last_error,
        }


class WikipediaConnector(InternetConnector):
    def __init__(self):
        self._id = "wikipedia"
        self._available = wikipedia is not None
        self._last_error: str | None = None

    @property
    def id(self) -> str:
        return self._id

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        if not self._available:
            return []

        results = []
        try:
            def _search():
                return wikipedia.search(query, results=max_results)

            titles = await asyncio.to_thread(_search)
            for title in titles:
                try:
                    page = await asyncio.to_thread(wikipedia.page, title, auto_suggest=False)
                    results.append(SearchResult(
                        title=page.title,
                        url=page.url,
                        snippet=(page.summary or "")[:300],
                        connector=self._id,
                        score=0.85,
                        metadata={"published": page.lastrevision.date if page.lastrevision else None},
                    ))
                except Exception:
                    pass
            self._last_error = None
        except Exception as e:
            self._last_error = str(e)
        return results[:max_results]

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._available and not self._last_error else "degraded" if self._available else "unavailable",
            "available": self._available,
            "last_error": self._last_error,
        }


class GitHubConnector(InternetConnector):
    def __init__(self, token: str | None = None):
        self._id = "github"
        self._available = aiohttp is not None
        self._token = token
        self._last_error: str | None = None

    @property
    def id(self) -> str:
        return self._id

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        if not self._available or not aiohttp:
            return []

        results = []
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            headers["Authorization"] = f"token {self._token}"

        try:
            from core.egress.aio import gated_session

            async with gated_session(headers=headers, source="internet.github") as session:
                url = "https://api.github.com/search/repositories"
                params = {"q": query, "per_page": max_results, "sort": "stars", "order": "desc"}
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data.get("items", []):
                            results.append(SearchResult(
                                title=item.get("full_name", ""),
                                url=item.get("html_url", ""),
                                snippet=(item.get("description") or "")[:300],
                                connector=self._id,
                                score=0.75,
                                metadata={"stars": item.get("stargazers_count"), "language": item.get("language")},
                            ))
                    else:
                        self._last_error = f"HTTP {resp.status}"
        except Exception as e:
            self._last_error = str(e)
        return results

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._available and not self._last_error else "degraded" if self._available else "unavailable",
            "available": self._available,
            "last_error": self._last_error,
        }


class RSSConnector(InternetConnector):
    def __init__(self, feed_urls: list[str]):
        self._id = "rss"
        self._feed_urls = feed_urls
        self._available = feedparser is not None
        self._last_error: str | None = None

    @property
    def id(self) -> str:
        return self._id

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        if not self._available:
            return []

        results = []
        query_terms = set(query.lower().split())

        try:
            for feed_url in self._feed_urls:
                feed = await asyncio.to_thread(feedparser.parse, feed_url)
                for entry in feed.entries[:max_results]:
                    title = entry.get("title", "")
                    snippet = entry.get("summary", "")[:300]
                    text = (title + " " + snippet).lower()
                    if query_terms & set(text.split()):
                        results.append(SearchResult(
                            title=title,
                            url=entry.get("link", ""),
                            snippet=snippet,
                            connector=self._id,
                            score=0.55,
                            metadata={"published": entry.get("published"), "feed": feed_url},
                        ))
            self._last_error = None
        except Exception as e:
            self._last_error = str(e)
        return results[:max_results]

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._available and not self._last_error else "degraded" if self._available else "unavailable",
            "available": self._available,
            "feeds": len(self._feed_urls),
            "last_error": self._last_error,
        }