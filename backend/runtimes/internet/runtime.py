from __future__ import annotations

import asyncio
import time
import hashlib
from typing import Any

from .contracts import (
    InternetRuntime,
    SearchQuery,
    SearchResult,
    ConnectorHealth,
    InternetConnector,
    InternetConnectorType,
    InternetStatus,
    InternetCache,
)
from .cache import InMemoryInternetCache, create_internet_cache


class BaseInternetConnector(InternetConnector):
    """Base class for internet connectors."""

    def __init__(self, connector_id: str, connector_type: InternetConnectorType):
        self._connector_id = connector_id
        self._connector_type = connector_type
        self._available = True
        self._last_error: str | None = None
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
    """DuckDuckGo search connector."""

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
        connector_id = f"rss_{hashlib.md5(feed_url.encode()).hexdigest()[:8]}"
        super().__init__(connector_id, InternetConnectorType.RSS)
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
            for entry in feed.entries[:query.max_results]:
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


class InternetRuntimeImpl(InternetRuntime):
    """Main Internet Runtime - owns retries, caching, provider selection, health, ranking."""

    def __init__(
        self,
        cache: InternetCache | None = None,
        max_retries: int = 3,
        cache_ttl: int = 900,
        connector_order: list[InternetConnectorType] | None = None,
    ):
        self._runtime_id = "internet"
        self._state = InternetStatus.INITIALIZING
        self._start_time = time.time()
        self._initialized = False

        self._cache = cache or InMemoryInternetCache()
        self._max_retries = max_retries
        self._cache_ttl = cache_ttl
        self._connector_order = connector_order or [
            InternetConnectorType.WIKIPEDIA,
            InternetConnectorType.GITHUB,
            InternetConnectorType.DUCKDUCKGO,
            InternetConnectorType.RSS,
        ]

        self._connectors: dict[str, InternetConnector] = {}
        self._stats = {
            "searches": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "connector_calls": 0,
            "connector_failures": 0,
            "total_latency_ms": 0.0,
        }

    async def initialize(self) -> None:
        self._state = InternetStatus.INITIALIZING
        # Register default connectors
        self.register_connector(DuckDuckGoConnector())
        self.register_connector(WikipediaConnector())
        self.register_connector(GitHubConnector())
        self._state = InternetStatus.READY
        self._initialized = True
        print(f"[InternetRuntime] Initialized with {len(self._connectors)} connectors")

    async def shutdown(self) -> None:
        self._state = InternetStatus.STOPPING
        self._state = InternetStatus.STOPPED

    def get_runtime_id(self) -> str:
        return self._runtime_id

    def get_metadata(self) -> dict[str, Any]:
        return {
            "runtime_id": self._runtime_id,
            "version": "1.0.0",
            "priority": "high",
            "capabilities": [
                "internet.search",
                "internet.connector.register",
                "internet.connector.unregister",
                "internet.health",
            ],
            "connectors": [c.get_connector_type().value for c in self._connectors.values()],
        }

    def get_state(self) -> InternetStatus:
        return self._state

    def health_check(self) -> dict[str, Any]:
        connector_health = {}
        for cid, conn in self._connectors.items():
            connector_health[cid] = asyncio.run(conn.health_check()) if hasattr(conn, 'health_check') else {"status": "unknown"}

        cache_stats = self._cache.stats() if hasattr(self._cache, 'stats') else {}

        return {
            "runtime_id": self._runtime_id,
            "state": self._state.value,
            "uptime_seconds": time.time() - self._start_time,
            "connectors": connector_health,
            "cache": cache_stats,
            "stats": self._stats,
        }

    def register_connector(self, connector: InternetConnector) -> None:
        if connector.get_connector_id() in self._connectors:
            raise ValueError(f"Connector {connector.get_connector_id()} already registered")
        self._connectors[connector.get_connector_id()] = connector
        print(f"[InternetRuntime] Registered connector: {connector.get_connector_id()} ({connector.get_connector_type().value})")

    def unregister_connector(self, connector_id: str) -> None:
        self._connectors.pop(connector_id, None)

    def _get_cache_key(self, query: SearchQuery) -> str:
        key = f"{query.query}:{query.max_results}:{query.language}:{query.region}:{query.safe_search}:{query.time_range}"
        return hashlib.md5(key.encode()).hexdigest()

    def _select_connectors(self, query: SearchQuery) -> list[InternetConnector]:
        if query.connector_types:
            selected = [
                c for c in self._connectors.values()
                if c.get_connector_type() in query.connector_types and c.is_available()
            ]
        else:
            selected = []
            for ctype in self._connector_order:
                for conn in self._connectors.values():
                    if conn.get_connector_type() == ctype and conn.is_available():
                        selected.append(conn)
                        break
        return selected

    async def _search_connector(self, connector: InternetConnector, query: SearchQuery) -> list[SearchResult]:
        last_error = None
        for attempt in range(self._max_retries):
            try:
                self._stats["connector_calls"] += 1
                results = await connector.search(query)
                return results
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    self._stats["connector_failures"] += 1
                    print(f"[InternetRuntime] Connector {connector.get_connector_id()} failed after {self._max_retries} attempts: {e}")
        return []

    def _rank_results(self, results: list[SearchResult], query: SearchQuery) -> list[SearchResult]:
        priority_map = {
            InternetConnectorType.WIKIPEDIA: 100,
            InternetConnectorType.GITHUB: 90,
            InternetConnectorType.DUCKDUCKGO: 70,
            InternetConnectorType.RSS: 60,
        }

        def rank_key(r: SearchResult):
            return (
                -r.score,
                -priority_map.get(r.connector_type, 50),
                -r.retrieved_at,
            )

        ranked = sorted(results, key=rank_key)
        return ranked[:query.max_results]

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        start = time.time()
        self._stats["searches"] += 1

        # Check cache
        cache_key = self._get_cache_key(query)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            self._stats["cache_hits"] += 1
            print(f"[InternetRuntime] Cache HIT for query: '{query.query[:50]}...'")
            self._stats["total_latency_ms"] += (time.time() - start) * 1000
            return cached

        self._stats["cache_misses"] += 1

        # Select connectors
        connectors = self._select_connectors(query)
        if not connectors:
            print(f"[InternetRuntime] No available connectors for query: '{query.query[:50]}...'")
            return []

        print(f"[InternetRuntime] Searching query: '{query.query[:50]}...' across {len(connectors)} connectors: {[c.get_connector_id() for c in connectors]}")

        # Search all connectors in parallel
        tasks = [self._search_connector(c, query) for c in connectors]
        connector_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[SearchResult] = []
        for i, result in enumerate(connector_results):
            if isinstance(result, Exception):
                print(f"[InternetRuntime] Connector {connectors[i].get_connector_id()} error: {result}")
            elif result:
                all_results.extend(result)

        # Rank and deduplicate
        ranked = self._rank_results(all_results, query)

        # Cache results
        await self._cache.set(cache_key, ranked, self._cache_ttl)

        self._stats["total_latency_ms"] += (time.time() - start) * 1000
        print(f"[InternetRuntime] Total results: {len(all_results)} -> ranked: {len(ranked)} (latency: {(time.time() - start) * 1000:.1f}ms)")
        return ranked


def create_internet_runtime(**kwargs) -> InternetRuntimeImpl:
    return InternetRuntimeImpl(**kwargs)