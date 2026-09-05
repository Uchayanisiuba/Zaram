from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
import time
import uuid


class InternetConnectorType(str, Enum):
    DUCKDUCKGO = "duckduckgo"
    #: Dated web results. Separate from `DUCKDUCKGO` because the distinction is
    #: the date, not the host: `text()` returns no publication date at all, so
    #: `relevance._recency_of` scored every general web result 0.5 — the value
    #: it uses for "undated", which its own curve makes identical to a page
    #: published 30 days ago. Recency was therefore a constant across the whole
    #: web shortlist and contributed nothing to the ordering, which is why
    #: answers read as though they came from the model's training data. `news()`
    #: carries a date per result and is what gives that ranker something to
    #: rank.
    NEWS = "news"
    WIKIPEDIA = "wikipedia"
    RSS = "rss"
    GITHUB = "github"
    GOOGLE = "google"
    BING = "bing"
    CUSTOM = "custom"


class InternetStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"
    DISABLED = "disabled"


@dataclass(frozen=True)
class SearchQuery:
    query: str
    max_results: int = 10
    connector_types: list[InternetConnectorType] | None = None
    language: str = "en"
    region: str = "us"
    safe_search: bool = True
    time_range: str | None = None


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    connector: str
    connector_type: InternetConnectorType
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    retrieved_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ConnectorHealth:
    connector_id: str
    connector_type: InternetConnectorType
    status: InternetStatus
    latency_ms: float = 0.0
    last_request: float = 0.0
    success_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    cache_hit_rate: float = 0.0


class InternetConnector(Protocol):
    async def search(self, query: SearchQuery) -> list[SearchResult]: ...
    async def health_check(self) -> ConnectorHealth: ...
    def get_connector_id(self) -> str: ...
    def get_connector_type(self) -> InternetConnectorType: ...
    def is_available(self) -> bool: ...


class InternetCache(Protocol):
    async def get(self, key: str) -> list[SearchResult] | None: ...
    async def set(self, key: str, value: list[SearchResult], ttl: int) -> None: ...
    async def clear(self) -> None: ...
    def stats(self) -> dict[str, Any]: ...


class InternetRanker(Protocol):
    async def rank(self, results: list[SearchResult], query: SearchQuery) -> list[SearchResult]: ...


class InternetRuntime(Protocol):
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def get_runtime_id(self) -> str: ...
    def get_metadata(self) -> dict[str, Any]: ...
    def get_state(self) -> InternetStatus: ...
    def health_check(self) -> dict[str, Any]: ...
    async def search(self, query: SearchQuery) -> list[SearchResult]: ...
    async def register_connector(self, connector: InternetConnector) -> None: ...
    async def unregister_connector(self, connector_id: str) -> None: ...
    async def get_connector_health(self, connector_id: str) -> ConnectorHealth | None: ...