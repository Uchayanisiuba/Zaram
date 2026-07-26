# backend/knowledge/providers/base.py
from __future__ import annotations

import time
from abc import abstractmethod
from typing import Any

from ..protocol import KnowledgeProvider, KnowledgeResult, ProviderStatus, ResultType


class BaseKnowledgeProvider(KnowledgeProvider):
    """Base class providing common functionality for all providers."""

    def __init__(self, provider_id: str, result_type: ResultType = ResultType.WEB, cache_ttl: int = 900):
        self._id = provider_id
        self._result_type = result_type
        self._cache_ttl = cache_ttl
        self._last_search_time = 0.0
        self._request_count = 0
        self._failure_count = 0

    @property
    def id(self) -> str:
        return self._id

    @property
    def result_type(self) -> ResultType:
        return self._result_type

    @property
    def cache_ttl(self) -> int:
        return self._cache_ttl

    def _record_success(self) -> None:
        self._request_count += 1
        self._last_search_time = time.time()

    def _record_failure(self) -> None:
        self._request_count += 1
        self._failure_count += 1

    def health(self) -> dict[str, Any]:
        base = super().health()
        base.update({
            "last_sync": self._last_search_time,
            "requests": self._request_count,
            "failures": self._failure_count,
            "cache_ttl": self._cache_ttl,
        })
        return base

    def metadata(self) -> dict[str, Any]:
        base = super().metadata()
        base.update({
            "type": self._result_type.value,
            "cache_ttl": self._cache_ttl,
        })
        return base


class SearchMixin:
    """Mixin providing common search utilities."""

    @staticmethod
    def make_result(
        title: str,
        url: str = "",
        snippet: str = "",
        provider: str = "",
        published: str | None = None,
        confidence: float = 0.8,
        result_type: ResultType = ResultType.WEB,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeResult:
        return KnowledgeResult(
            title=title,
            url=url,
            snippet=snippet,
            provider=provider,
            published=published,
            confidence=confidence,
            type=result_type,
            metadata=metadata or {},
        )
